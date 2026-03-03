# weavemo-backend-mock/routers/comments.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from dependencies.auth import get_current_user
from dependencies.premium import require_premium
from db.database import get_supabase

router = APIRouter(prefix="/posts", tags=["comments"])


@router.get("/{post_id}/comments")
def list_comments(
    post_id: int,
    current_user=Depends(get_current_user),  # 로그인 필수
    supabase=Depends(get_supabase),
):
    # 게시글 존재/공개 체크
    post_res = (
        supabase.table("posts")
        .select("id, visibility")
        .eq("id", post_id)
        .eq("visibility", "public")
        .limit(1)
        .execute()
    )
    if not (post_res.data or []):
        raise HTTPException(status_code=404, detail="Post not found")

    res = (
        supabase.table("comments")
        .select("id, post_id, user_id, content, created_at, is_anon")
        .eq("post_id", post_id)
        .order("created_at", desc=False)
        .order("id", desc=False)
        .execute()
    )

    items = res.data or []
    for c in items:
        c["isMine"] = (c.get("user_id") == current_user["user_id"])
        c["authorDisplayName"] = "익명" if c.get("is_anon") else "user"  # TODO: nickname
        c["isAnonymous"] = bool(c.get("is_anon"))

    return {"items": items}


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

    # 1) 댓글 insert
    res = (
        supabase.table("comments")
        .insert(
            {
                "post_id": post_id,
                "user_id": current_user["user_id"],
                "content": body.get("content"),
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

    row["isMine"] = True
    row["authorDisplayName"] = "익명" if is_anon else "user"
    row["isAnonymous"] = is_anon
    return row
