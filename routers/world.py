# routers/world.py

import logging
from uuid import UUID

from pydantic import BaseModel, Field
from fastapi import APIRouter, Body, Depends, HTTPException

from db.database import get_supabase
from dependencies.auth import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/initialize")
def initialize_world(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    user_id = current_user["user_id"]

    try:
        # 요청 본문에서 사용자 ID를 받지 않는다.
        # 기존 World와 동물이 있으면 현재 상태를 반환한다.
        result = supabase.rpc(
            "initialize_my_world",
            {
                "p_user_id": user_id,
            },
        ).execute()
    except Exception as error:
        logger.exception("World initialization failed")

        raise HTTPException(
            status_code=503,
            detail="Could not initialize world",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid world response",
        )

    world = data.get("world")
    companion = data.get("companion")

    if (
        not isinstance(world, dict)
        or not isinstance(companion, dict)
        or str(world.get("user_id")) != str(user_id)
        or str(companion.get("user_id")) != str(user_id)
        or not isinstance(world.get("terrain_key"), str)
        or world.get("visibility") not in (
            "private",
            "friends",
            "public",
        )
        or companion.get("stage") not in (
            "egg",
            "hatched",
            "grown",
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid world response",
        )

    return data

# 알 돌보기를 현지 날짜별로 한 번 기록한다.
@router.post("/companion/warm")
def warm_companion(
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
        # 인증된 본인의 알만 돌볼 수 있다.
        result = supabase.rpc(
            "warm_my_companion",
            {
                "p_user_id": current_user["user_id"],
                "p_tz_offset_min": tz_offset_min,
            },
        ).execute()
    except Exception as error:
        logger.exception("Companion warming failed")

        raise HTTPException(
            status_code=503,
            detail="Could not care for companion",
        ) from error

    data = result.data

    if (
        not isinstance(data, dict)
        or data.get("ok") is not True
        or data.get("completed") is not True
        or data.get("activity_source") != "companion_warm"
        or data.get("tz_offset_min") != tz_offset_min
        or not isinstance(data.get("local_date"), str)
        or not isinstance(data.get("recorded_at"), str)
        or not isinstance(data.get("already_completed"), bool)
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid companion care response",
        )

    return data
# 성장 시간 신호의 요청 형식을 정의한다.
class CompanionGrowthHeartbeatRequest(BaseModel):
    connection_id: UUID
    tz_offset_min: int = Field(
        ...,
        ge=-840,
        le=840,
        strict=True,
    )
    active: bool = Field(..., strict=True)


@router.post("/companion/growth/heartbeat")
def companion_growth_heartbeat(
    body: CompanionGrowthHeartbeatRequest,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        # 사용자 ID와 누적 시간은 클라이언트에서 받지 않는다.
        result = supabase.rpc(
            "heartbeat_companion_growth",
            {
                "p_user_id": current_user["user_id"],
                "p_connection_id": str(body.connection_id),
                "p_tz_offset_min": body.tz_offset_min,
                "p_active": body.active,
            },
        ).execute()
    except Exception as error:
        logger.exception("Companion growth heartbeat failed")

        raise HTTPException(
            status_code=503,
            detail="Could not update companion growth",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid companion growth response",
        )

    total_ms = data.get("egg_active_ms")
    added_ms = data.get("added_ms")

    if (
        type(data.get("initialized")) is not bool
        or type(data.get("eligible")) is not bool
        or data.get("reason") not in (
            "world_not_initialized",
            "another_connection",
            "growing",
            "not_egg",
            "inactive",
            "care_required",
        )
        or type(total_ms) is not int
        or total_ms < 0
        or type(added_ms) is not int
        or not 0 <= added_ms <= 35000
        or added_ms > total_ms
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid companion growth response",
        )

    return data

# 성장 상태를 변경하지 않고 현재 누적 시간만 조회한다.
@router.get("/companion/growth")
def get_companion_growth(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        result = (
            supabase.table("companion_growth_state")
            .select("egg_active_ms")
            .eq("user_id", current_user["user_id"])
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.exception("Companion growth lookup failed")

        raise HTTPException(
            status_code=503,
            detail="Could not load companion growth",
        ) from error

    rows = result.data

    if not isinstance(rows, list):
        raise HTTPException(
            status_code=503,
            detail="Invalid companion growth response",
        )

    # 아직 성장 신호를 받지 않았다면 누적 시간은 0이다.
    total_ms = rows[0].get("egg_active_ms") if rows else 0

    if type(total_ms) is not int or total_ms < 0:
        raise HTTPException(
            status_code=503,
            detail="Invalid companion growth response",
        )

    return {"egg_active_ms": total_ms}
