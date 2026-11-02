# routers/dust.py

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from db.database import get_supabase
from dependencies.auth import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)

MAX_BIGINT = 9223372036854775807


@router.get("/transactions")
def list_my_dust_transactions(
    limit: int = Query(20, ge=1, le=50),
    before_id: int | None = Query(
        None,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    # 요청에서 사용자 ID를 받지 않고 인증된 본인만 조회한다.
    query = (
        supabase.table("dust_transactions")
        .select(
            "id, source, source_id, amount, "
            "balance_before, balance_after, created_at"
        )
        .eq("user_id", current_user["user_id"])
        .order("id", desc=True)
        .limit(limit + 1)
    )

    if before_id is not None:
        query = query.lt("id", before_id)

    try:
        result = query.execute()
    except Exception as error:
        logger.exception("Dust transaction lookup failed")

        raise HTTPException(
            status_code=503,
            detail="Could not load dust transactions",
        ) from error

    rows = result.data or []
    has_more = len(rows) > limit
    visible_rows = rows[:limit]

    # 큰 정수 식별자는 프론트에서 정밀도가 손실되지 않도록 문자열로 보낸다.
    items = [
        {
            "id": str(row["id"]),
            "source": row["source"],
            "source_id": row["source_id"],
            "amount": row["amount"],
            "balance_before": row["balance_before"],
            "balance_after": row["balance_after"],
            "created_at": row["created_at"],
        }
        for row in visible_rows
    ]

    return {
        "items": items,
        "next_cursor": (
            items[-1]["id"]
            if has_more and items
            else None
        ),
    }
