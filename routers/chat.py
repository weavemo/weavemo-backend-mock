# weavemo-backend-mock/routers/chat.py

from typing import Literal
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

class ChatInvitationActionRequest(BaseModel):
    action: Literal["accept", "decline"]

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
            "invalid_action": (
                400,
                "Invalid invitation action",
            ),
            "invitation_pending": (
                409,
                "Waiting for the recipient to accept",
            ),
            "invitation_accept_required": (
                403,
                "Accept the invitation before replying",
            ),
            "invitation_declined": (
                403,
                "Conversation invitation was declined",
            ),
            "invitation_not_allowed": (
                403,
                "Only the recipient can respond to this invitation",
            ),
            "invitation_not_pending": (
                409,
                "This invitation has already been processed",
            ),
            "invitation_not_ready": (
                409,
                "The invitation has no message yet",
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


# weavemo-backend-mock/routers/chat.py
# 기존 open_direct_chat 함수 교체

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

    conversation_id = data.get("conversation_id")
    invitation_status = data.get("invitation_status")
    requested_by = data.get("requested_by")

    if (
        not is_valid_id(conversation_id)
        or data.get("kind") != "direct"
        or invitation_status not in (
            "pending",
            "accepted",
            "declined",
        )
        or (
            requested_by is not None
            and not is_valid_id(requested_by)
        )
        or (
            invitation_status in ("pending", "declined")
            and requested_by is None
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid conversation response",
        )

    return {
        "conversation_id": conversation_id,
        "kind": "direct",
        "invitation_status": invitation_status,
        "requested_by": requested_by,
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

# weavemo-backend-mock/routers/chat.py
# 기존 코드 맨 아래에 추가

@router.get("/invitations")
def list_chat_invitations(
    before_id: int | None = Query(
        default=None,
        ge=1,
        le=MAX_BIGINT,
    ),
    limit: int = Query(default=20, ge=1, le=50),
    current_user=Depends(get_current_user),
):
    data = call_chat_rpc(
        "weavemo_list_chat_invitations",
        {
            "p_actor": current_user["user_id"],
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
            detail="Invalid invitation response",
        )

    for item in items:
        if (
            not isinstance(item, dict)
            or not is_valid_id(item.get("conversation_id"))
            or not is_valid_id(item.get("sender_id"))
            or not is_valid_id(item.get("message_id"))
            or not isinstance(item.get("nickname"), str)
            or not isinstance(item.get("body"), str)
            or not isinstance(item.get("created_at"), str)
        ):
            raise HTTPException(
                status_code=503,
                detail="Invalid invitation response",
            )

    return {
        "items": items,
        "next_cursor": next_cursor,
    }


@router.post("/conversations/{conversation_id}/invitation")
def respond_to_chat_invitation(
    body: ChatInvitationActionRequest,
    conversation_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
):
    data = call_chat_rpc(
        "weavemo_chat_invitation_action",
        {
            "p_actor": current_user["user_id"],
            "p_conversation_id": conversation_id,
            "p_action": body.action,
        },
    )

    expected_status = (
        "accepted" if body.action == "accept" else "declined"
    )

    if (
        data.get("conversation_id") != str(conversation_id)
        or data.get("invitation_status") != expected_status
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid invitation response",
        )

    return {
        "conversation_id": data["conversation_id"],
        "invitation_status": data["invitation_status"],
    }
# weavemo-backend-mock/routers/chat.py
# 기존 코드 맨 아래에 추가

@router.get("/conversations/{conversation_id}/state")
def get_chat_state(
    conversation_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
):
    data = call_chat_rpc(
        "weavemo_get_chat_state",
        {
            "p_actor": current_user["user_id"],
            "p_conversation_id": conversation_id,
        },
    )

    if (
        data.get("conversation_id") != str(conversation_id)
        or data.get("kind") != "direct"
        or data.get("invitation_status") not in (
            "pending",
            "accepted",
            "declined",
        )
        or (
            data.get("requested_by") is not None
            and not is_valid_id(data["requested_by"])
        )
        or (
            data.get("ended_at") is not None
            and not isinstance(data["ended_at"], str)
        )
        or (
            data.get("ended_by") is not None
            and not is_valid_id(data["ended_by"])
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid conversation state",
        )

    return {
        "conversation_id": data["conversation_id"],
        "kind": data["kind"],
        "invitation_status": data["invitation_status"],
        "requested_by": data.get("requested_by"),
        "ended_at": data.get("ended_at"),
        "ended_by": data.get("ended_by"),
    }
