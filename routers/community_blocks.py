# routers/community_blocks.py

from fastapi import APIRouter, Depends, HTTPException, Path

from db.database import get_supabase
from dependencies.auth import get_current_user
from routers.friends import change_user_block
from services.post_access import require_post_access, users_are_blocked


router = APIRouter()
MAX_BIGINT = 9223372036854775807


def block_content_author(
    supabase,
    current_user: dict,
    content: dict,
) -> dict:
    actor_id = int(current_user["user_id"])
    target_id = int(content["user_id"])

    if actor_id == target_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot block yourself",
        )

    # 기존 차단 목록에서 익명 작성자의 신원이 드러나지 않게 한다.
    if content.get("is_anon"):
        raise HTTPException(
            status_code=400,
            detail="Anonymous author blocking unavailable",
        )

    result = change_user_block(
        actor_id,
        target_id,
        "block",
    )

    if result.get("blocked") is not True:
        raise HTTPException(
            status_code=503,
            detail="Could not block author",
        )

    # 작성자 ID나 닉네임은 응답에 포함하지 않는다.
    return {"blocked": True}


@router.post("/{post_id}/block-author")
def block_post_author(
    post_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    post = require_post_access(
        supabase,
        post_id,
        current_user,
    )

    return block_content_author(
        supabase,
        current_user,
        post,
    )


@router.post("/{post_id}/comments/{comment_id}/block-author")
def block_comment_author(
    post_id: int = Path(..., ge=1, le=MAX_BIGINT),
    comment_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    # 댓글이 속한 게시물의 공개 범위와 접근 권한을 먼저 검사한다.
    require_post_access(
        supabase,
        post_id,
        current_user,
    )

    result = (
        supabase.table("comments")
        .select("id, post_id, user_id, content, is_anon")
        .eq("id", comment_id)
        .eq("post_id", post_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Comment not found",
        )

    comment = result.data[0]

    if comment.get("content") == "[deleted]":
        raise HTTPException(
            status_code=404,
            detail="Comment not found",
        )

    if users_are_blocked(
        supabase,
        int(current_user["user_id"]),
        int(comment["user_id"]),
    ):
        raise HTTPException(
            status_code=404,
            detail="Comment not found",
        )

    return block_content_author(
        supabase,
        current_user,
        comment,
    )
