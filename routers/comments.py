# weavemo-backend-mock/routers/comments.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
import time
import httpx
from services.post_access import require_post_access

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
    return {"items": [_comment_to_dto(c, current_user) for c in rows]}


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

    post = post_res.data[0]
    is_anon = bool(body.get("isAnonymous", False))
    content = (body.get("content") or "").strip()
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
    return _comment_to_dto(row, current_user)
