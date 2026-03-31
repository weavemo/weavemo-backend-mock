# weavemo-backend-mock/routers/comments_actions.py
from fastapi import APIRouter, Depends, HTTPException

from dependencies.auth import get_current_user
from db.database import get_supabase

router = APIRouter()


@router.delete("/{comment_id}")
def delete_comment(
    comment_id: int,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    # 댓글 조회
    c_res = (
        supabase.table("comments")
        .select("id, user_id, post_id, content")
        .eq("id", comment_id)
        .limit(1)
        .execute()
    )
    if not (c_res.data or []):
        raise HTTPException(status_code=404, detail="Comment not found")

    c = c_res.data[0]
    if c.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not allowed")

    # 이미 삭제된 댓글이면 멱등
    if (c.get("content") or "") == "[deleted]":
        return {"deleted": True}

    # soft delete
    supabase.table("comments").update({"content": "[deleted]"}).eq("id", comment_id).execute()

    # posts.comments_count -1
    p_res = (
        supabase.table("posts")
        .select("id, comments_count, visibility")
        .eq("id", c["post_id"])
        .limit(1)
        .execute()
    )
    if p_res.data and p_res.data[0].get("visibility") == "public":
        new_cc = max(0, int(p_res.data[0].get("comments_count") or 0) - 1)
        supabase.table("posts").update({"comments_count": new_cc}).eq("id", c["post_id"]).execute()

    return {"deleted": True}
