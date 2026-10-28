# weavemo-backend-mock/routers/notes.py

import logging

from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_BIGINT = 9223372036854775807


class SendNoteRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    client_message_id: UUID
    reply_to_id: int | None = Field(
        default=None,
        ge=1,
        le=MAX_BIGINT,
    )
class NoteSettingsRequest(BaseModel):
    receive_scope: Literal["friends", "requests"]


class NoteRequestAction(BaseModel):
    action: Literal["accept", "decline"]

def is_valid_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and len(value) <= 19
        and 1 <= int(value) <= MAX_BIGINT
    )


def call_notes_rpc(name: str, params: dict) -> dict:
    try:
        result = get_supabase().rpc(name, params).execute()
    except APIError as error:
        logger.exception("Notes RPC failed: %s", name)

        raise HTTPException(
            status_code=503,
            detail="Notes service unavailable",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid note response",
        )

    error_code = data.get("error")

    if error_code:
        errors = {
            "invalid_request": (
                400,
                "Invalid note request",
            ),
            "self_not_allowed": (
                400,
                "Cannot send a note to yourself",
            ),
            "invalid_body": (
                400,
                "Note must contain between 1 and 2000 characters",
            ),
            "not_available": (
                404,
                "User or note not available",
            ),
            "friends_required": (
                403,
                "Only friends can exchange notes",
            ),
            "reply_not_available": (
                404,
                "Reply target not available",
            ),
            "message_conflict": (
                409,
                "Message ID was already used for another note",
            ),
            "retry_required": (
                503,
                "Please retry sending the note",
            ),
            "requests_not_allowed": (
                403,
                "This user does not accept new note requests",
            ),
            "request_pending": (
                409,
                "Waiting for the recipient to accept your note request",
            ),
            "request_accept_required": (
                403,
                "Accept the note request before replying",
            ),
            "request_declined": (
                403,
                "This note request was declined",
            ),
            "request_not_allowed": (
                403,
                "Only the recipient can respond to this note request",
            ),
            "request_not_pending": (
                409,
                "This note request has already been processed",
            ),
        }

        status_code, detail = errors.get(
            error_code,
            (503, "Notes service unavailable"),
        )

        raise HTTPException(
            status_code=status_code,
            detail=detail,
        )

    return data


@router.post("/to/{target_user_id}")
def send_note(
    body: SendNoteRequest,
    target_user_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]

    data = call_notes_rpc(
        "weavemo_send_friend_note",
        {
            "p_actor": user_id,
            "p_target": target_user_id,
            "p_body": body.body,
            "p_client_message_id": str(body.client_message_id),
            "p_reply_to_id": body.reply_to_id,
        },
    )

    expected_reply_id = (
        str(body.reply_to_id)
        if body.reply_to_id is not None
        else None
    )

    if (
        not is_valid_id(data.get("id"))
        or data.get("sender_id") != str(user_id)
        or data.get("recipient_id") != str(target_user_id)
        or data.get("client_message_id") != str(body.client_message_id)
        or data.get("reply_to_id") != expected_reply_id
        or not isinstance(data.get("body"), str)
        or not isinstance(data.get("created_at"), str)
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid note response",
        )

    return {
        "id": data["id"],
        "sender_id": data["sender_id"],
        "recipient_id": data["recipient_id"],
        "body": data["body"],
        "client_message_id": data["client_message_id"],
        "reply_to_id": data["reply_to_id"],
        "created_at": data["created_at"],
    }
# weavemo-backend-mock/routers/notes.py
# 기존 코드 맨 아래에 추가

@router.get("/settings")
def get_note_settings(
    current_user=Depends(get_current_user),
):
    try:
        result = (
            get_supabase()
            .table("users")
            .select("note_receive_scope")
            .eq("id", current_user["user_id"])
            .limit(1)
            .execute()
        )
    except APIError as error:
        logger.exception("Note settings lookup failed")

        raise HTTPException(
            status_code=503,
            detail="Could not load note settings",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="User not available",
        )

    scope = result.data[0].get("note_receive_scope")

    if scope not in ("friends", "requests"):
        raise HTTPException(
            status_code=503,
            detail="Invalid note settings",
        )

    return {"receive_scope": scope}


@router.put("/settings")
def update_note_settings(
    body: NoteSettingsRequest,
    current_user=Depends(get_current_user),
):
    try:
        result = (
            get_supabase()
            .table("users")
            .update({
                "note_receive_scope": body.receive_scope,
            })
            .eq("id", current_user["user_id"])
            .execute()
        )
    except APIError as error:
        logger.exception("Note settings update failed")

        raise HTTPException(
            status_code=503,
            detail="Could not save note settings",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="User not available",
        )

    if (
        result.data[0].get("note_receive_scope")
        != body.receive_scope
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid note settings response",
        )

    return {"receive_scope": body.receive_scope}


@router.post("/requests/{request_id}/respond")
def respond_to_note_request(
    body: NoteRequestAction,
    request_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
):
    data = call_notes_rpc(
        "weavemo_note_request_action",
        {
            "p_actor": current_user["user_id"],
            "p_request_id": request_id,
            "p_action": body.action,
        },
    )

    expected_status = (
        "accepted" if body.action == "accept" else "declined"
    )

    if (
        data.get("request_id") != str(request_id)
        or data.get("status") != expected_status
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid note request response",
        )

    return {
        "request_id": data["request_id"],
        "status": data["status"],
    }
# weavemo-backend-mock/routers/notes.py
# 기존 코드 맨 아래에 추가

@router.get("")
def list_notes(
    box: Literal["inbox", "sent", "requests"] = "inbox",
    before_id: int | None = Query(
        default=None,
        ge=1,
        le=MAX_BIGINT,
    ),
    limit: int = Query(default=20, ge=1, le=50),
    current_user=Depends(get_current_user),
):
    user_id = str(current_user["user_id"])

    data = call_notes_rpc(
        "weavemo_list_friend_notes",
        {
            "p_actor": current_user["user_id"],
            "p_box": box,
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
            detail="Invalid note list response",
        )

    for item in items:
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=503,
                detail="Invalid note list response",
            )

        valid = (
            is_valid_id(item.get("id"))
            and is_valid_id(item.get("sender_id"))
            and is_valid_id(item.get("recipient_id"))
            and is_valid_id(item.get("peer_id"))
            and isinstance(item.get("nickname"), str)
            and isinstance(item.get("body"), str)
            and isinstance(item.get("created_at"), str)
            and (
                item.get("read_at") is None
                or isinstance(item["read_at"], str)
            )
            and (
                item.get("reply_to_id") is None
                or is_valid_id(item["reply_to_id"])
            )
            and (
                item.get("request_id") is None
                or is_valid_id(item["request_id"])
            )
            and item.get("request_status") in (
                None,
                "pending",
                "accepted",
                "declined",
            )
        )

        if box == "sent":
            valid = (
                valid
                and item.get("sender_id") == user_id
                and item.get("peer_id") == item.get("recipient_id")
            )
        else:
            valid = (
                valid
                and item.get("recipient_id") == user_id
                and item.get("peer_id") == item.get("sender_id")
            )

        if not valid:
            raise HTTPException(
                status_code=503,
                detail="Invalid note list response",
            )

    return {
        "items": items,
        "next_cursor": next_cursor,
    }
# weavemo-backend-mock/routers/notes.py
# 기존 코드 맨 아래에 추가

@router.get("/counts")
def get_note_counts(
    current_user=Depends(get_current_user),
):
    data = call_notes_rpc(
        "weavemo_note_counts",
        {"p_actor": current_user["user_id"]},
    )

    counts = {}

    for key in ("unread_count", "request_count"):
        value = data.get(key)

        if (
            not isinstance(value, str)
            or not value.isascii()
            or not value.isdecimal()
            or len(value) > 19
        ):
            raise HTTPException(
                status_code=503,
                detail="Invalid note count response",
            )

        counts[key] = min(int(value), 9007199254740991)

    return counts


@router.post("/{note_id}/open")
def open_note(
    note_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
):
    user_id = str(current_user["user_id"])

    data = call_notes_rpc(
        "weavemo_open_friend_note",
        {
            "p_actor": current_user["user_id"],
            "p_note_id": note_id,
        },
    )

    if (
        data.get("id") != str(note_id)
        or not is_valid_id(data.get("sender_id"))
        or not is_valid_id(data.get("recipient_id"))
        or not is_valid_id(data.get("peer_id"))
        or not isinstance(data.get("nickname"), str)
        or not isinstance(data.get("body"), str)
        or not isinstance(data.get("created_at"), str)
        or (
            data.get("read_at") is not None
            and not isinstance(data["read_at"], str)
        )
        or (
            data.get("reply_to_id") is not None
            and not is_valid_id(data["reply_to_id"])
        )
        or (
            data.get("request_id") is not None
            and not is_valid_id(data["request_id"])
        )
        or data.get("request_status") not in (
            None,
            "pending",
            "accepted",
            "declined",
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid note response",
        )

    if data["sender_id"] == user_id:
        expected_peer = data["recipient_id"]
    elif data["recipient_id"] == user_id:
        expected_peer = data["sender_id"]
    else:
        raise HTTPException(
            status_code=503,
            detail="Invalid note participant response",
        )

    if data["peer_id"] != expected_peer:
        raise HTTPException(
            status_code=503,
            detail="Invalid note participant response",
        )

    return {
        "id": data["id"],
        "sender_id": data["sender_id"],
        "recipient_id": data["recipient_id"],
        "peer_id": data["peer_id"],
        "nickname": data["nickname"],
        "profile_image_url": data.get("profile_image_url"),
        "body": data["body"],
        "reply_to_id": data.get("reply_to_id"),
        "request_id": data.get("request_id"),
        "request_status": data.get("request_status"),
        "created_at": data["created_at"],
        "read_at": data.get("read_at"),
    }
# weavemo-backend-mock/routers/notes.py
# 기존 코드 맨 아래에 추가

@router.delete("/{note_id}")
def delete_note(
    note_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
):
    result = get_supabase().rpc(
        "weavemo_delete_friend_note",
        {
            "p_actor": int(current_user["user_id"]),
            "p_note_id": note_id,
        },
    ).execute()

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Could not delete note",
        )

    if data.get("error") == "not_available":
        raise HTTPException(
            status_code=404,
            detail="Note not available",
        )

    if data.get("error"):
        raise HTTPException(
            status_code=400,
            detail="Could not delete note",
        )

    if (
        data.get("deleted") is not True
        or data.get("id") != str(note_id)
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid delete response",
        )

    return {
        "id": str(note_id),
        "deleted": True,
    }
