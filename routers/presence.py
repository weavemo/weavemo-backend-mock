# weavemo-backend-mock/routers/presence.py

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_BIGINT = 9223372036854775807


class PresenceHeartbeatRequest(BaseModel):
    connection_id: UUID


class FriendPresenceRequest(BaseModel):
    user_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
    )


def call_presence_rpc(name: str, params: dict) -> dict:
    try:
        result = get_supabase().rpc(name, params).execute()
    except APIError as error:
        logger.exception("Presence RPC failed: %s", name)

        raise HTTPException(
            status_code=503,
            detail="Presence service unavailable",
        ) from error

    data = result.data

    if not isinstance(data, dict) or data.get("error"):
        raise HTTPException(
            status_code=503,
            detail="Invalid presence response",
        )

    return data


@router.post("/heartbeat")
def presence_heartbeat(
    body: PresenceHeartbeatRequest,
    current_user=Depends(get_current_user),
):
    data = call_presence_rpc(
        "weavemo_presence_heartbeat",
        {
            "p_actor": current_user["user_id"],
            "p_connection_id": str(body.connection_id),
        },
    )

    if data.get("connected") is not True:
        raise HTTPException(
            status_code=503,
            detail="Invalid presence response",
        )

    return {"connected": True}


@router.post("/friends")
def get_friend_presence(
    body: FriendPresenceRequest,
    current_user=Depends(get_current_user),
):
    target_ids = []

    for value in body.user_ids:
        if (
            not value.isascii()
            or not value.isdecimal()
            or len(value) > 19
            or not 1 <= int(value) <= MAX_BIGINT
        ):
            raise HTTPException(
                status_code=422,
                detail="Invalid user ID",
            )

        target_ids.append(int(value))

    target_ids = list(dict.fromkeys(target_ids))

    data = call_presence_rpc(
        "weavemo_friend_presence",
        {
            "p_actor": current_user["user_id"],
            "p_target_ids": target_ids,
        },
    )

    items = data.get("items")
    allowed_ids = {str(value) for value in target_ids}

    if not isinstance(items, list):
        raise HTTPException(
            status_code=503,
            detail="Invalid presence response",
        )

    for item in items:
        if (
            not isinstance(item, dict)
            or item.get("id") not in allowed_ids
            or not isinstance(item.get("online"), bool)
        ):
            raise HTTPException(
                status_code=503,
                detail="Invalid presence response",
            )

    return {"items": items}


@router.delete("/connections")
def clear_my_presence(
    current_user=Depends(get_current_user),
):
    try:
        (
            get_supabase()
            .table("user_presence_connections")
            .delete()
            .eq("user_id", current_user["user_id"])
            .execute()
        )
    except APIError as error:
        logger.exception("Presence cleanup failed")

        raise HTTPException(
            status_code=503,
            detail="Could not clear presence",
        ) from error

    return {"cleared": True}
