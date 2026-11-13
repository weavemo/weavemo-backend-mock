# weavemo-backend-mock/routers/comments.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
import time
import httpx
from services.post_access import require_post_access
from routers.friends import get_blocked_ids
from services.hidden_content import get_hidden_content_ids
from dependencies.auth import get_current_user
from dependencies.premium import require_premium
from db.database import get_supabase

router = APIRouter()

def _execute_with_retry(builder, tries: int = 2):
    """
    Windows에서 가끔 나는 httpx.ReadError(WinError 10035) 완화용.
    GET/조회성 요청은 재시도해도 안전(idempotent)하므로 1~2회만 재시도.
    """
    last = None
    for i in range(tries):
        try:
            return builder.execute()
        except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last = e
            time.sleep(0.15 * (i + 1))
    raise last

def _attach_comment_author_names(supabase, rows: list[dict]) -> None:
    author_ids = {
        int(row["user_id"])
        for row in rows
        if not row.get("is_anon") and row.get("user_id") is not None
    }

    authors = {}

    if author_ids:
        result = (
            supabase.table("users")
            .select("id, nickname, profile_image_url")
            .in_("id", sorted(author_ids))
            .execute()
        )

        authors = {
            int(user["id"]): user
            for user in (result.data or [])
        }

    for row in rows:
        if row.get("is_anon"):
            row["_author_name"] = "익명"
            row["_author_avatar_url"] = None
            continue

        user_id = row.get("user_id")
        author = authors.get(int(user_id), {}) if user_id is not None else {}
        row["_author_name"] = (author.get("nickname") or "").strip() or "user"
        row["_author_avatar_url"] = (
            author.get("profile_image_url")
            if row.get("content") != "[deleted]"
            else None
        )
        
def _comment_to_dto(c: dict, current_user: dict) -> dict:
    is_anon = bool(c.get("is_anon"))
    return {
        "id": c.get("id"),
        "postId": c.get("post_id"),
        "content": c.get("content") or "",
        "createdAt": c.get("created_at"),
        "authorDisplayName": (
            "익명" if is_anon else c.get("_author_name", "user")
        ),
        "isAnonymous": is_anon,
        "authorAvatarUrl": (
            c.get("_author_avatar_url")
            if not is_anon and c.get("content") != "[deleted]"
            else None
        ),
        "authorUserId": (
            str(c["user_id"])
            if not is_anon
            and c.get("user_id") is not None
            and c.get("content") != "[deleted]"
            else None
        ),
        "isMine": (c.get("user_id") == current_user["user_id"]),
    }

@router.get("/{post_id}/comments")
def list_comments(
    post_id: int,
    current_user=Depends(get_current_user),  # 로그인 필수
    supabase=Depends(get_supabase),
):
    # 댓글 조회 전에 게시물 공개 범위와 양방향 차단 검사
    require_post_access(
        supabase,
        post_id,
        current_user,
    )

    res = _execute_with_retry(
        supabase.table("comments")
        .select("id, post_id, user_id, content, created_at, is_anon")
        .eq("post_id", post_id)
        .order("created_at", desc=False)
        .order("id", desc=False)
    )

    rows = res.data or []
    viewer_id = int(current_user["user_id"])

    author_ids = sorted({
        int(row["user_id"])
        for row in rows
        if int(row["user_id"]) != viewer_id
    })

    # 어느 한쪽이라도 차단한 관계라면 해당 작성자의 댓글을 숨긴다.
    blocked_ids = {
        int(user_id)
        for user_id in get_blocked_ids(
            supabase,
            viewer_id,
            author_ids,
        )
    }

    # 현재 사용자가 개별적으로 숨긴 댓글 번호를 조회한다.
    hidden_comment_ids = get_hidden_content_ids(
        supabase,
        viewer_id,
        "comment",
        [int(row["id"]) for row in rows],
    )

    # 작성자 차단과 개별 댓글 숨김을 모두 적용한다.
    visible_rows = [
        row
        for row in rows
        if int(row["user_id"]) not in blocked_ids
        and int(row["id"]) not in hidden_comment_ids
    ]

    # 차단 필터를 통과한 댓글에만 작성자 표시 이름을 붙인다.
    _attach_comment_author_names(supabase, visible_rows)

    return {
        "items": [
            _comment_to_dto(row, current_user)
            for row in visible_rows
        ]
    }


@router.post("/{post_id}/comments")
def create_comment(
    post_id: int,
    body: dict,
    current_user=Depends(require_premium),  # 프리미엄만
    supabase=Depends(get_supabase),
):
    # 댓글 작성 전에 게시물 공개 범위와 양방향 차단 검사
    post = require_post_access(
        supabase,
        post_id,
        current_user,
    )

    is_anon = bool(body.get("isAnonymous", False))
    content = (body.get("content") or "").strip()
    
    # 응원 댓글 여부
    is_encouragement = body.get("isEncouragement") is True
    
    # 응원은 공개 댓글로만 작성
    if is_encouragement and is_anon:
        raise HTTPException(
            status_code=400,
            detail="Encouragement cannot be anonymous",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Content required")
    if len(content) > 500:
        raise HTTPException(status_code=400, detail="Content too long")
    
    # 저장 요청은 자동 재시도하지 않는다.
    # 서버에서 저장된 뒤 응답만 유실됐을 때 중복 생성되는 것을 방지한다.
    res = (
        supabase.table("comments")
        .insert({
            "post_id": post_id,
            "user_id": current_user["user_id"],
            "content": content,
            "is_anon": is_anon,
            "created_at": datetime.utcnow().isoformat(),
            "is_encouragement": is_encouragement,
        })
        .execute()
    )

    row = (res.data or [None])[0]
    if not row:
        raise HTTPException(status_code=500, detail="Insert failed")

    # 2) posts.comments_count +1 (MVP: 경쟁상황 레이스는 일단 허용)
    new_cc = int(post.get("comments_count") or 0) + 1
    _execute_with_retry(
        supabase.table("posts")
        .update({"comments_count": new_cc})
        .eq("id", post_id)
    )
    # 일반 댓글에만 10P 지급
    # 응원 댓글 5P는 공감·응원 통합 보상 함수에서 처리할 예정
    if not is_encouragement:
        try:
            import logging
            from datetime import timezone
    
            event_res = (
                supabase.table("quest_activity_events")
                .insert({
                    "user_id": current_user["user_id"],
                    "activity_source": "community_comment",
                    "source_id": str(row["id"]),
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                })
                .execute()
            )
    
            event = (event_res.data or [None])[0]
    
            if event:
                supabase.rpc(
                    "grant_activity_points",
                    {
                        "p_user_id": current_user["user_id"],
                        "p_event_id": event["id"],
                        "p_tz_offset_min": -420,
                    },
                ).execute()
    
        except Exception:
            logging.getLogger(__name__).exception(
                "Community comment point reward failed"
            )

    _attach_comment_author_names(supabase, [row])
    return _comment_to_dto(row, current_user)

