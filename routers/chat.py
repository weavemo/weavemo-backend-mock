# weavemo-backend-mock/routers/chat.py

import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from postgrest.exceptions import APIError

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_BIGINT = 9223372036854775807


@router.post("/direct/{target_user_id}")
def open_direct_chat(
    target_user_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    supabase = get_supabase()

    try:
        result = supabase.rpc(
            "weavemo_open_direct_chat",
            {
                "p_actor": user_id,
                "p_target": target_user_id,
            },
        ).execute()
    except APIError as error:
        logger.exception("Opening direct chat failed")

        raise HTTPException(
            status_code=503,
            detail="Could not open conversation",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid conversation response",
        )

    error_code = data.get("error")

    if error_code:
        errors = {
            "self_not_allowed": (
                400,
                "Cannot start a conversation with yourself",
            ),
            "not_found": (
                404,
                "User not available",
            ),
            "unavailable": (
                404,
                "User not available",
            ),
            "friends_required": (
                403,
                "Only friends can start a conversation",
            ),
        }

        status_code, detail = errors.get(
            error_code,
            (503, "Could not open conversation"),
        )

        raise HTTPException(
            status_code=status_code,
            detail=detail,
        )

    conversation_id = data.get("conversation_id")

    if (
        not isinstance(conversation_id, str)
        or not conversation_id.isdecimal()
        or not 1 <= int(conversation_id) <= MAX_BIGINT
        or data.get("kind") != "direct"
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid conversation response",
        )

    return {
        "conversation_id": conversation_id,
        "kind": "direct",
    }
