# routers/quests.py

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from db.database import get_supabase
from dependencies.auth import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/daily")
def get_my_daily_quests(
    tz_offset_min: int = Query(..., ge=-840, le=840),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        # 요청에서 사용자 ID를 받지 않고 인증된 본인만 조회한다.
        result = supabase.rpc(
            "get_daily_quest_progress",
            {
                "p_user_id": current_user["user_id"],
                "p_tz_offset_min": tz_offset_min,
            },
        ).execute()
    except Exception as error:
        logger.exception("Daily quest lookup failed")

        raise HTTPException(
            status_code=503,
            detail="Could not load daily quests",
        ) from error

    data = result.data

    if (
        not isinstance(data, dict)
        or not isinstance(data.get("items"), list)
        or not isinstance(data.get("local_date"), str)
        or data.get("tz_offset_min") != tz_offset_min
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid daily quest response",
        )

    return data
