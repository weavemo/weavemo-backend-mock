# routers/hidden_content.py

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from postgrest.exceptions import APIError

from services.post_access import require_post_access, users_are_blocked
from db.database import get_supabase
from dependencies.auth import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)

MAX_BIGINT = 9223372036854775807


@router.get("")
def list_hidden_content(
    limit: int = Query(default=20, ge=1, le=50),
    before_id: int | None = Query(
        default=None,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    user_id = int(current_user["user_id"])

    try:
        query = (
            supabase.table("user_hidden_content")
            .select("id, content_kind, created_at")
            .eq("user_id", user_id)
            .order("id", desc=True)
            .limit(limit + 1)
        )

        if before_id is not None:
            query = query.lt("id", before_id)

        result = query.execute()
        rows = result.data or []
        page = rows[:limit]

        # 숨긴 항목의 작성자 정보나 원문은 조회하지 않는다.
        return {
            "items": [
                {
                    "id": str(row["id"]),
                    "content_kind": row["content_kind"],
                    "created_at": row["created_at"],
                }
                for row in page
            ],
            "next_cursor": (
                str(page[-1]["id"])
                if len(rows) > limit and page
                else None
            ),
        }

    except Exception as error:
        logger.exception("Hidden content list failed")

        raise HTTPException(
            status_code=503,
            detail="Could not load hidden content",
        ) from error


@router.delete("/{hidden_id}")
def restore_hidden_content(
    hidden_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    user_id = int(current_user["user_id"])

    try:
        # 본인 소유의 숨김 기록만 해제한다.
        # 이미 해제된 항목에 다시 요청해도 같은 결과를 반환한다.
        (
            supabase.table("user_hidden_content")
            .delete()
            .eq("id", hidden_id)
            .eq("user_id", user_id)
            .execute()
        )

    except Exception as error:
        logger.exception("Hidden content restore failed")

        raise HTTPException(
            status_code=503,
            detail="Could not restore hidden content",
        ) from error

    # 해제는 기존 공개 범위나 차단 권한을 변경하지 않는다.
    return {
        "id": str(hidden_id),
        "hidden": False,
    }

def save_hidden_content(
    supabase,
    user_id: int,
    post_id: int,
    comment_id: int | None,
) -> dict:
    kind = "comment" if comment_id is not None else "post"

    try:
        # 저장 요청은 자동 재시도하지 않는다.
        (
            supabase.table("user_hidden_content")
            .insert({
                "user_id": user_id,
                "content_kind": kind,
                "post_id": post_id,
                "comment_id": comment_id,
            })
            .execute()
        )

    except APIError as error:
        if str(error.code) == "23505":
            # 같은 항목이 이미 숨겨졌는지 확인한다.
            query = (
                supabase.table("user_hidden_content")
                .select("id")
                .eq("user_id", user_id)
                .eq("content_kind", kind)
                .eq("post_id", post_id)
            )

            if comment_id is not None:
                query = query.eq("comment_id", comment_id)

            existing = query.limit(1).execute()

            if existing.data:
                return {"hidden": True}

        logger.exception("Hidden content insert failed")
        raise HTTPException(
            status_code=503,
            detail="Could not hide content",
        ) from error

    return {"hidden": True}


def validate_hide_target(content: dict, user_id: int) -> None:
    if int(content["user_id"]) == user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot hide your own content",
        )

    # 이번 숨김 기능은 익명 콘텐츠에 적용한다.
    if content.get("is_anon") is not True:
        raise HTTPException(
            status_code=400,
            detail="Content is not anonymous",
        )


@router.post("/posts/{post_id}")
def hide_post(
    post_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        post = require_post_access(
            supabase,
            post_id,
            current_user,
        )

        user_id = int(current_user["user_id"])
        validate_hide_target(post, user_id)

        return save_hidden_content(
            supabase,
            user_id,
            post_id,
            None,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.exception("Post hide request failed")
        raise HTTPException(
            status_code=503,
            detail="Could not hide content",
        ) from error


@router.post("/posts/{post_id}/comments/{comment_id}")
def hide_comment(
    post_id: int = Path(..., ge=1, le=MAX_BIGINT),
    comment_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
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

        user_id = int(current_user["user_id"])

        if users_are_blocked(
            supabase,
            user_id,
            int(comment["user_id"]),
        ):
            raise HTTPException(
                status_code=404,
                detail="Comment not found",
            )

        validate_hide_target(comment, user_id)

        return save_hidden_content(
            supabase,
            user_id,
            post_id,
            comment_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.exception("Comment hide request failed")
        raise HTTPException(
            status_code=503,
            detail="Could not hide content",
        ) from error
