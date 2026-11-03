# routers/quests.py

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import APIRouter, Body, Depends, HTTPException, Query
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

# 미스터리 퀘스트를 배정하거나 오늘의 기존 배정을 반환한다.
@router.post("/mystery/assign")
def assign_my_daily_mystery_quest(
    tz_offset_min: int = Body(
        ...,
        embed=True,
        ge=-840,
        le=840,
        strict=True,
    ),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        # 사용자 ID는 요청에서 받지 않고 인증 정보에서 가져온다.
        result = supabase.rpc(
            "assign_daily_mystery_quest",
            {
                "p_user_id": current_user["user_id"],
                "p_tz_offset_min": tz_offset_min,
            },
        ).execute()
    except Exception as error:
        logger.exception("Daily mystery quest assignment failed")

        raise HTTPException(
            status_code=503,
            detail="Could not assign daily mystery quest",
        ) from error

    data = result.data

    if (
        not isinstance(data, dict)
        or not isinstance(data.get("local_date"), str)
        or "assignment" not in data
        or (
            data["assignment"] is not None
            and not isinstance(data["assignment"], dict)
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid mystery quest response",
        )

    return data
