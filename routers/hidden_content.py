# routers/hidden_content.py

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query

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
