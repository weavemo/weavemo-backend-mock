# routers/world.py

import logging
from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Body, Depends, HTTPException, Query

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

    validate_care_reward(data)
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

# 저장된 성장 시간과 서버 설정으로 남은 부화 시간을 계산한다.
@router.get("/companion/growth")
def get_companion_growth(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        growth_result = (
            supabase.table("companion_growth_state")
            .select("egg_active_ms")
            .eq("user_id", current_user["user_id"])
            .limit(1)
            .execute()
        )

        settings_result = (
            supabase.table("companion_growth_settings")
            .select("required_active_ms,display_duration_ms")
            .eq("key", "default")
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.exception("Companion growth lookup failed")

        raise HTTPException(
            status_code=503,
            detail="Could not load companion growth",
        ) from error

    growth_rows = growth_result.data
    settings_rows = settings_result.data

    if (
        not isinstance(growth_rows, list)
        or not isinstance(settings_rows, list)
        or len(settings_rows) != 1
        or not isinstance(settings_rows[0], dict)
        or (
            growth_rows
            and not isinstance(growth_rows[0], dict)
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid companion growth response",
        )

    total_ms = (
        growth_rows[0].get("egg_active_ms")
        if growth_rows
        else 0
    )

    settings = settings_rows[0]
    required_ms = settings.get("required_active_ms")
    display_ms = settings.get("display_duration_ms")

    if (
        type(total_ms) is not int
        or total_ms < 0
        or type(required_ms) is not int
        or required_ms <= 0
        or type(display_ms) is not int
        or display_ms <= 0
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid companion growth settings",
        )

    remaining_active_ms = max(0, required_ms - total_ms)

    # 정수 계산으로 남은 표시 시간을 올림 처리한다.
    remaining_display_ms = (
        display_ms * remaining_active_ms + required_ms - 1
    ) // required_ms

    return {
        "egg_active_ms": total_ms,
        "required_active_ms": required_ms,
        "display_duration_ms": display_ms,
        "remaining_active_ms": remaining_active_ms,
        "remaining_display_ms": remaining_display_ms,
        "ready_to_hatch": remaining_active_ms == 0,
    }

# 서버의 누적 시간 조건을 확인한 뒤 동물을 부화시킨다.
@router.post("/companion/hatch")
def hatch_companion(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    user_id = current_user["user_id"]

    try:
        result = supabase.rpc(
            "hatch_my_companion",
            {
                "p_user_id": user_id,
            },
        ).execute()
    except Exception as error:
        logger.exception("Companion hatching failed")

        raise HTTPException(
            status_code=503,
            detail="Could not hatch companion",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid companion hatch response",
        )

    # 시간 미충족은 정상적인 처리 결과로 반환한다.
    if data.get("ok") is False:
        remaining_ms = data.get("remaining_active_ms")

        if (
            data.get("reason") != "not_ready"
            or type(remaining_ms) is not int
            or remaining_ms <= 0
        ):
            raise HTTPException(
                status_code=503,
                detail="Invalid companion hatch response",
            )

        return data

    companion = data.get("companion")

    if (
        data.get("ok") is not True
        or type(data.get("already_hatched")) is not bool
        or not isinstance(companion, dict)
        or str(companion.get("user_id")) != str(user_id)
        or companion.get("stage") not in ("hatched", "grown")
        or not isinstance(companion.get("species_key"), str)
        or not companion["species_key"].strip()
        or not isinstance(companion.get("hatched_at"), str)
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid companion hatch response",
        )

    return data

# 부화 후 사용할 돌봄 종류.
# 부화 후 돌봄 활동과 공통 기록의 연결.
CARE_SOURCES = {
    "feed": "companion_feed",
    "water": "companion_water",
    "play": "companion_play",
    "sleep": "companion_sleep",
    "comfort": "companion_comfort",
    "praise": "companion_praise",
}


class CompanionCareRequest(BaseModel):
    action: Literal[
        "feed",
        "water",
        "play",
        "sleep",
        "comfort",
        "praise",
    ]
    tz_offset_min: int = Field(
        ...,
        ge=-840,
        le=840,
        strict=True,
    )


@router.post("/companion/care")
def care_companion(
    body: CompanionCareRequest,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        result = supabase.rpc(
            "care_my_companion",
            {
                "p_user_id": current_user["user_id"],
                "p_tz_offset_min": body.tz_offset_min,
                "p_action": body.action,
            },
        ).execute()
    except Exception as error:
        logger.exception("Companion care failed")
        raise HTTPException(
            status_code=503,
            detail="Could not save companion care",
        ) from error

    data = result.data

    if (
        isinstance(data, dict)
        and data.get("ok") is False
        and data.get("reason") == "not_hatched"
    ):
        raise HTTPException(
            status_code=409,
            detail="Companion has not hatched",
        )

    if (
        not isinstance(data, dict)
        or data.get("ok") is not True
        or data.get("action") != body.action
        or data.get("completed") is not True
        or not isinstance(data.get("local_date"), str)
        or type(data.get("already_completed")) is not bool
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid companion care response",
        )

    validate_care_reward(data)
    return data


@router.get("/companion/care")
def get_companion_care(
    tz_offset_min: int = Query(..., ge=-840, le=840),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
     # 브라우저와 같은 오프셋으로 오늘의 조회 범위를 계산한다.。
    offset = timedelta(minutes=tz_offset_min)
    today = (datetime.now(timezone.utc) + offset).date()
    start = datetime.combine(
        today, datetime.min.time(), tzinfo=timezone.utc
    ) - offset
    end = start + timedelta(days=1)

    try:
        result = (
            supabase.table("quest_activity_events")
            .select("activity_source")
            .eq("user_id", current_user["user_id"])
            .eq("source_id", f"daily:{today.isoformat()}")
            .in_("activity_source", list(CARE_SOURCES.values()))
            .gte("occurred_at", start.isoformat())
            .lt("occurred_at", end.isoformat())
            .execute()
        )

        rows = result.data

        if not isinstance(rows, list) or any(
            not isinstance(row, dict)
            or row.get("activity_source") not in CARE_SOURCES.values()
            for row in rows
        ):
            raise ValueError("Invalid care records")

        sources = {row["activity_source"] for row in rows}
    except Exception as error:
        logger.exception("Companion care lookup failed")
        raise HTTPException(
            status_code=503,
            detail="Could not load companion care",
        ) from error

    return {
        "local_date": today.isoformat(),
        "completed_actions": [
            action
            for action, source in CARE_SOURCES.items()
            if source in sources
        ],
    }

# 돌봄 응답에 포함된 공통 포인트 결과를 검증한다.
def validate_care_reward(data: dict) -> None:
    gained = data.get("points_gained")
    balance = data.get("point_balance")
    already_completed = data.get("already_completed")
    reason = data.get("reward_reason")

    if (
        type(gained) is not int
        or gained < 0
        or type(balance) is not int
        or balance < 0
        or gained > balance
        or type(already_completed) is not bool
        or reason not in (
            "granted",
            "already_completed",
            "already_granted",
            "rule_not_found",
            "rule_disabled",
            "zero_reward",
            "event_not_today",
            "daily_limit",
        )
        or (already_completed and gained != 0)
        or (reason == "granted" and gained <= 0)
        or (reason != "granted" and gained != 0)
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid care reward response",
        )

# 홈에서 돌봄 미완료 여부와 공통 포인트를 조회한다.
@router.get("/summary")
def get_world_summary(
    tz_offset_min: int = Query(..., ge=-840, le=840),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    user_id = current_user["user_id"]
    offset = timedelta(minutes=tz_offset_min)
    today = (datetime.now(timezone.utc) + offset).date()

    start = datetime.combine(
        today, datetime.min.time(), tzinfo=timezone.utc
    ) - offset
    end = start + timedelta(days=1)

    try:
        companions = (
            supabase.table("user_companions")
            .select("stage")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )

        wallets = (
            supabase.table("user_point_wallets")
            .select("balance")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )

        if (
            not isinstance(companions, list)
            or not isinstance(wallets, list)
        ):
            raise ValueError("Invalid summary records")

        stage = companions[0]["stage"] if companions else None
        balance = wallets[0]["balance"] if wallets else 0

        if (
            stage not in (None, "egg", "hatched", "grown")
            or type(balance) is not int
            or balance < 0
        ):
            raise ValueError("Invalid summary values")

        if stage == "egg":
            required = {"companion_warm"}
        elif stage in ("hatched", "grown"):
            required = set(CARE_SOURCES.values())
        else:
            required = set()

        # World가 없으면 첫 방문을 안내한다.
        pending = stage is None

        if required:
            events = (
                supabase.table("quest_activity_events")
                .select("activity_source")
                .eq("user_id", user_id)
                .eq("source_id", f"daily:{today.isoformat()}")
                .in_("activity_source", sorted(required))
                .gte("occurred_at", start.isoformat())
                .lt("occurred_at", end.isoformat())
                .execute()
                .data
            )

            if not isinstance(events, list):
                raise ValueError("Invalid care records")

            completed = {row["activity_source"] for row in events}
            pending = not required.issubset(completed)

    except Exception as error:
        logger.exception("World summary lookup failed")
        raise HTTPException(
            status_code=503,
            detail="Could not load world summary",
        ) from error

    return {
        "local_date": today.isoformat(),
        "stage": stage,
        "has_pending_care": pending,
        "point_balance": balance,
    }
