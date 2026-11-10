from routers.world_story import router as world_story_router
from routers.world_layout import router as world_layout_router
import logging
from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query

from db.database import get_supabase
from dependencies.auth import get_current_user
from routers.token_exchange import router as token_exchange_router


router = APIRouter()
router.include_router(world_layout_router)
logger = logging.getLogger(__name__)
router.include_router(token_exchange_router, prefix="/tokens")
router.include_router(world_story_router, prefix="/story")


@router.post("/initialize")
def initialize_world(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    user_id = current_user["user_id"]

    try:
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

@router.get("/companion/growth")
def get_companion_growth(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        result = supabase.rpc(
            "get_companion_growth_status",
            {
                "p_user_id": current_user["user_id"],
            },
        ).execute()

        data = result.data

        numeric_keys = (
            "egg_active_ms",
            "egg_effective_ms",
            "required_active_ms",
            "display_duration_ms",
            "remaining_active_ms",
            "remaining_display_ms",
        )

        if not isinstance(data, dict):
            raise ValueError("Invalid growth response")

        if any(
            type(data.get(key)) is not int
            or data[key] < 0
            for key in numeric_keys
        ):
            raise ValueError("Invalid growth values")

        if (
            data["required_active_ms"] <= 0
            or data["display_duration_ms"] <= 0
            or type(data.get("ready_to_hatch")) is not bool
            or not isinstance(data.get("thermal"), dict)
            or data["thermal"].get("ok") is not True
        ):
            raise ValueError("Invalid growth settings")

        return data

    except Exception as error:
        logger.exception("Companion growth lookup failed")
        raise HTTPException(
            status_code=503,
            detail="Could not load companion growth",
        ) from error

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


@router.post("/friends/{target_user_id}/warm")
def help_friend_egg(
    target_user_id: int = Path(..., ge=1, le=9223372036854775807),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        result = supabase.rpc(
            "help_friend_companion",
            {
                "p_actor": int(current_user["user_id"]),
                "p_target": target_user_id,
            },
        ).execute()
    except Exception as error:
        logger.exception("Friend companion help failed")
        raise HTTPException(
            status_code=503,
            detail={"reason": "help_unavailable"},
        ) from error

    data = result.data
    if not isinstance(data, dict) or type(data.get("ok")) is not bool:
        raise HTTPException(status_code=503, detail={"reason": "invalid_response"})

    if data["ok"]:
        if type(data.get("already_helped")) is not bool:
            raise HTTPException(status_code=503, detail={"reason": "invalid_response"})
        return {"ok": True, "already_helped": data["already_helped"]}

    reason = data.get("reason")
    statuses = {
        "invalid_request": 400,
        "self_not_allowed": 400,
        "unavailable": 404,
        "care_not_started": 409,
        "ready_to_hatch": 409,
        "warmth_full": 409,
    }
    if not isinstance(reason, str) or reason not in statuses:
        raise HTTPException(status_code=503, detail={"reason": "invalid_response"})
    raise HTTPException(status_code=statuses[reason], detail={"reason": reason})
