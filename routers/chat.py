# weavemo-backend-mock/routers/chat.py

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Path, Query
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

class MarkChatReadRequest(BaseModel):
    message_id: int = Field(ge=1, le=MAX_BIGINT)

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

# weavemo-backend-mock/routers/chat.py
# 기존 코드 맨 아래에 추가

@router.get("/conversations/{conversation_id}/messages")
def list_chat_messages(
    conversation_id: int = Path(..., ge=1, le=MAX_BIGINT),
    before_id: int | None = Query(
        default=None,
        ge=1,
        le=MAX_BIGINT,
    ),
    limit: int = Query(default=30, ge=1, le=50),
    current_user=Depends(get_current_user),
):
    data = call_chat_rpc(
        "weavemo_list_chat_messages",
        {
            "p_actor": current_user["user_id"],
            "p_conversation_id": conversation_id,
            "p_before_id": before_id,
            "p_limit": limit,
        },
    )

    items = data.get("items")
    next_cursor = data.get("next_cursor")

    if (
        not isinstance(items, list)
        or len(items) > limit
        or (
            next_cursor is not None
            and not is_valid_id(next_cursor)
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid message list response",
        )

    for message in items:
        if not isinstance(message, dict):
            raise HTTPException(
                status_code=503,
                detail="Invalid message list response",
            )

        sender_id = message.get("sender_id")

        if (
            not is_valid_id(message.get("id"))
            or message.get("conversation_id") != str(conversation_id)
            or (
                sender_id is not None
                and not is_valid_id(sender_id)
            )
            or not isinstance(message.get("body"), str)
            or not isinstance(message.get("client_message_id"), str)
            or not isinstance(message.get("created_at"), str)
        ):
            raise HTTPException(
                status_code=503,
                detail="Invalid message list response",
            )

    return {
        "items": items,
        "next_cursor": next_cursor,
    }
# weavemo-backend-mock/routers/chat.py
# 기존 코드 맨 아래에 추가

@router.get("/unread-count")
def get_chat_unread_count(
    current_user=Depends(get_current_user),
):
    data = call_chat_rpc(
        "weavemo_chat_unread_count",
        {"p_actor": current_user["user_id"]},
    )

    count = data.get("count")

    if (
        not isinstance(count, str)
        or not count.isascii()
        or not count.isdecimal()
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid unread count response",
        )

    # 브라우저에서 안전하게 표현 가능한 정수 범위로 제한한다.
    return {"count": min(int(count), 9007199254740991)}


@router.put("/conversations/{conversation_id}/read")
def mark_chat_read(
    body: MarkChatReadRequest,
    conversation_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
):
    data = call_chat_rpc(
        "weavemo_mark_chat_read",
        {
            "p_actor": current_user["user_id"],
            "p_conversation_id": conversation_id,
            "p_message_id": body.message_id,
        },
    )

    if (
        data.get("conversation_id") != str(conversation_id)
        or not is_valid_id(data.get("last_read_message_id"))
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid read response",
        )

    return {
        "conversation_id": data["conversation_id"],
        "last_read_message_id": data["last_read_message_id"],
    }
