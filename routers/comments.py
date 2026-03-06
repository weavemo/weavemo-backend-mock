# weavemo-backend-mock/routers/comments.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
import time
import httpx
from postgrest.exceptions import APIError

from dependencies.auth import get_current_user
from dependencies.premium import require_premium
from db.database import get_supabase

router = APIRouter(prefix="/posts", tags=["comments"])

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
def _comment_to_dto(c: dict, current_user: dict) -> dict:
    is_anon = bool(c.get("is_anon"))
    return {
        "id": c.get("id"),
        "postId": c.get("post_id"),
        "content": c.get("content") or "",
        "createdAt": c.get("created_at"),
        "authorDisplayName": "익명" if is_anon else "user",  # TODO: nickname
        "isAnonymous": is_anon,
        "isMine": (c.get("user_id") == current_user["user_id"]),
    }

@router.get("/{post_id}/comments")
def list_comments(
    post_id: int,
    current_user=Depends(get_current_user),  # 로그인 필수
    supabase=Depends(get_supabase),
):
   # ✅ Supabase 호출 2번 -> 1번으로 감소
    # comments -> posts FK join으로 "공개글의 댓글만" 가져오기
    # (posts가 없거나 public이 아니면 0 rows)
    res = _execute_with_retry(
        supabase.table("comments")
        .select("id, post_id, user_id, content, created_at, is_anon, posts!inner(id, visibility)")
        .eq("post_id", post_id)
        .eq("posts.visibility", "public")
        .order("created_at", desc=False)
        .order("id", desc=False)
    )

    rows = res.data or []
    # posts가 없거나 public이 아니면 댓글도 0개로 내려오는데,
    # "없는 글"이면 404로 유지하고 싶으면 아래처럼 처리
    if not rows:
        # 댓글이 0개인 공개글과, 존재하지 않는 글을 구분하려면 posts를 한번 더 조회해야 함.
        # 여기서는 기존 동작을 최대한 유지하기 위해 posts 조회 1번만 딱 더 한다(댓글 0일 때만).
        post_res = _execute_with_retry(
            supabase.table("posts")
            .select("id, visibility")
            .eq("id", post_id)
            .eq("visibility", "public")
            .limit(1)
        )
        if not (post_res.data or []):
            raise HTTPException(status_code=404, detail="Post not found")

    return {"items": [_comment_to_dto(c, current_user) for c in rows]}


@router.post("/{post_id}/comments")
def create_comment(
    post_id: int,
    body: dict,
    current_user=Depends(require_premium),  # 프리미엄만
    supabase=Depends(get_supabase),
):
    # 게시글 존재/공개 체크
    post_res = (
        supabase.table("posts")
        .select("id, comments_count, visibility")
        .eq("id", post_id)
        .eq("visibility", "public")
        .limit(1)
        .execute()
    )
    if not (post_res.data or []):
        raise HTTPException(status_code=404, detail="Post not found")

    post = post_res.data[0]
    is_anon = bool(body.get("isAnonymous", False))
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content required")
    if len(content) > 500:
        raise HTTPException(status_code=400, detail="Content too long")
    
    # 1) 댓글 insert
    res = (
        supabase.table("comments")
        .insert(
            {
                "post_id": post_id,
                "user_id": current_user["user_id"],
                "content": content,
                "is_anon": is_anon,
                "created_at": datetime.utcnow().isoformat(),
            }
        )
        .execute()
    )

    row = (res.data or [None])[0]
    if not row:
        raise HTTPException(status_code=500, detail="Insert failed")

    # 2) posts.comments_count +1 (MVP: 경쟁상황 레이스는 일단 허용)
    new_cc = int(post.get("comments_count") or 0) + 1
    supabase.table("posts").update({"comments_count": new_cc}).eq("id", post_id).execute()

    return _comment_to_dto(row, current_user)
