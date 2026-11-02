# weavemo-backend-mock/routers/comments_actions.py


from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path
from pydantic import BaseModel, ConfigDict, Field

from services.post_access import require_post_access
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

# 댓글 수정은 본문만 허용한다.
class UpdateCommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=500)


@router.patch("/{comment_id}")
def update_comment(
    body: UpdateCommentRequest,
    comment_id: int = Path(
        ...,
        ge=1,
        le=9223372036854775807,
    ),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    content = body.content.strip()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Content required",
        )

    # 삭제 표시로 사용하는 문자열은 본문으로 저장하지 않는다.
    if content == "[deleted]":
        raise HTTPException(
            status_code=400,
            detail="Reserved content",
        )

    result = (
        supabase.table("comments")
        .select("id, user_id, post_id, content")
        .eq("id", comment_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Comment not found",
        )

    comment = result.data[0]
    actor_id = int(current_user["user_id"])

    if int(comment["user_id"]) != actor_id:
        raise HTTPException(
            status_code=403,
            detail="Not allowed",
        )

    if comment.get("content") == "[deleted]":
        raise HTTPException(
            status_code=404,
            detail="Comment not found",
        )

    # 게시물 접근 권한이 있는 경우에만 댓글을 수정한다.
    require_post_access(
        supabase,
        int(comment["post_id"]),
        current_user,
    )

    # 조회 후 삭제된 댓글을 다시 살리지 않도록 조건부 수정한다.
    # 저장 요청은 자동 재시도하지 않는다.
    updated = (
        supabase.table("comments")
        .update({"content": content})
        .eq("id", comment_id)
        .eq("user_id", actor_id)
        .neq("content", "[deleted]")
        .execute()
    )

    if not updated.data:
        raise HTTPException(
            status_code=409,
            detail="Comment changed or deleted",
        )

    row = updated.data[0]

    # 댓글 수와 작성 시각, 익명 여부는 변경하지 않는다.
    return {
        "id": row["id"],
        "postId": row["post_id"],
        "content": row["content"],
    }
