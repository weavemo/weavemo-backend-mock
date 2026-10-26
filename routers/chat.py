# weavemo-backend-mock/routers/chat.py

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_BIGINT = 9223372036854775807


class SendMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    client_message_id: UUID


def call_chat_rpc(function_name: str, params: dict) -> dict:
    try:
        result = get_supabase().rpc(
            function_name,
            params,
        ).execute()
    except APIError as error:
        logger.exception("Chat RPC failed: %s", function_name)

        raise HTTPException(
            status_code=503,
            detail="Chat service unavailable",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid chat response",
        )

    error_code = data.get("error")

    if error_code:
        errors = {
            "self_not_allowed": (
                400,
                "Cannot start a conversation with yourself",
            ),
            "invalid_request": (
                400,
                "Invalid message request",
            ),
            "invalid_body": (
                400,
                "Message must contain between 1 and 2000 characters",
            ),
            "not_found": (
                404,
                "Conversation or user not available",
            ),
            "unavailable": (
                404,
                "Conversation or user not available",
            ),
            "not_available": (
                403,
                "Messaging is not available",
            ),
            "friends_required": (
                403,
                "Only friends can chat",
            ),
            "message_conflict": (
                409,
                "Message ID was already used for another message",
            ),
            "retry_required": (
                503,
                "Please retry sending the message",
            ),
        }

        status_code, detail = errors.get(
            error_code,
            (503, "Chat service unavailable"),
        )

        raise HTTPException(
            status_code=status_code,
            detail=detail,
        )

    return data


def is_valid_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and 1 <= int(value) <= MAX_BIGINT
    )


@router.post("/direct/{target_user_id}")
def open_direct_chat(
    target_user_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
):
    data = call_chat_rpc(
        "weavemo_open_direct_chat",
        {
            "p_actor": current_user["user_id"],
            "p_target": target_user_id,
        },
    )

    if (
        not is_valid_id(data.get("conversation_id"))
        or data.get("kind") != "direct"
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid conversation response",
        )

    return {
        "conversation_id": data["conversation_id"],
        "kind": "direct",
    }


@router.post("/conversations/{conversation_id}/messages")
def send_chat_message(
    body: SendMessageRequest,
    conversation_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]

    data = call_chat_rpc(
        "weavemo_send_chat_message",
        {
            "p_actor": user_id,
            "p_conversation_id": conversation_id,
            "p_body": body.body,
            "p_client_message_id": str(body.client_message_id),
        },
    )

    if (
        not is_valid_id(data.get("id"))
        or data.get("conversation_id") != str(conversation_id)
        or data.get("sender_id") != str(user_id)
        or not isinstance(data.get("body"), str)
        or data.get("client_message_id") != str(body.client_message_id)
        or not isinstance(data.get("created_at"), str)
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid message response",
        )

    return {
        "id": data["id"],
        "conversation_id": data["conversation_id"],
        "sender_id": data["sender_id"],
        "body": data["body"],
        "client_message_id": data["client_message_id"],
        "created_at": data["created_at"],
    }
