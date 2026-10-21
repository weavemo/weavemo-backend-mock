# routers/notifications.py

import base64
import logging
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config.settings import settings
from db.database import get_supabase
from dependencies.auth import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class SubscriptionRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=4096)
    keys: SubscriptionKeys


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=4096)


def validate_endpoint(endpoint: str) -> str:
    try:
        parsed = urlsplit(endpoint)

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or parsed.port not in (None, 443)
            or any(character.isspace() for character in endpoint)
        ):
            raise ValueError("Invalid endpoint")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid push endpoint",
        ) from None

    return endpoint


def decode_key(value: str) -> bytes:
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, base64.binascii.Error):
        raise HTTPException(
            status_code=400,
            detail="Invalid push subscription key",
        ) from None


def validate_keys(keys: SubscriptionKeys) -> None:
    public_key = decode_key(keys.p256dh)
    auth_secret = decode_key(keys.auth)

    if (
        len(public_key) != 65
        or public_key[0] != 4
        or len(auth_secret) != 16
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid push subscription key",
        )

    try:
        ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(),
            public_key,
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid push public key",
        ) from None


@router.get("/public-key")
def get_public_key(
    current_user=Depends(get_current_user),
):
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=503,
            detail="Push notifications are not configured",
        )

    return {"publicKey": settings.VAPID_PUBLIC_KEY}


@router.post("/subscriptions")
def register_subscription(
    body: SubscriptionRequest,
    current_user=Depends(get_current_user),
):
    endpoint = validate_endpoint(body.endpoint)
    validate_keys(body.keys)

    supabase = get_supabase()
    user_id = current_user["user_id"]

    try:
        # endpoint와 사용자 ID를 함께 충돌 기준으로 사용하지 않는다.
        # 동일 구독이 서로 다른 계정에 중복 등록되는 것을 막는다.
        supabase.table("push_subscriptions").insert({
            "user_id": user_id,
            "endpoint": endpoint,
            "p256dh": body.keys.p256dh,
            "auth": body.keys.auth,
        }).execute()

    except Exception as error:
        if str(getattr(error, "code", "")) != "23505":
            logger.error(
                "Push registration failed: %s",
                type(error).__name__,
            )
            raise HTTPException(
                status_code=503,
                detail="Could not register push subscription",
            ) from None

        # 이미 등록된 구독은 현재 사용자 소유일 때만 갱신한다.
        try:
            from datetime import datetime, timezone

            result = (
                supabase.table("push_subscriptions")
                .update({
                    "p256dh": body.keys.p256dh,
                    "auth": body.keys.auth,
                    "updated_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                })
                .eq("endpoint", endpoint)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as update_error:
            logger.error(
                "Push subscription update failed: %s",
                type(update_error).__name__,
            )
            raise HTTPException(
                status_code=503,
                detail="Could not update push subscription",
            ) from None

        if not result.data:
            raise HTTPException(
                status_code=409,
                detail="Push subscription belongs to another account",
            )

    return {"registered": True}


@router.delete("/subscriptions")
def unregister_subscription(
    body: UnsubscribeRequest,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    try:
        (
            supabase.table("push_subscriptions")
            .delete()
            .eq("endpoint", body.endpoint)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as error:
        logger.error(
            "Push subscription removal failed: %s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not remove push subscription",
        ) from None

    return {"removed": True}

# routers/notifications.py
# 기존 코드 맨 아래에 추가

from datetime import datetime, timezone
from fastapi import Query


@router.get("/inbox")
def get_notification_inbox(
    limit: int = Query(default=20, ge=1, le=50),
    before_id: int | None = Query(default=None, ge=1),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    try:
        query = (
            supabase.table("user_notifications")
            .select(
                "id, kind, title, body, target_path, "
                "local_date, created_at, read_at"
            )
            .eq("user_id", user_id)
            .order("id", desc=True)
            .limit(limit + 1)
        )

        if before_id is not None:
            query = query.lt("id", before_id)

        result = query.execute()
        rows = result.data or []

        has_more = len(rows) > limit
        items = rows[:limit]

        return {
            "items": items,
            "next_cursor": (
                items[-1]["id"]
                if has_more and items
                else None
            ),
        }

    except Exception as error:
        logger.error(
            "Notification inbox load failed: %s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not load notification inbox",
        ) from None


@router.get("/inbox/unread-count")
def get_notification_unread_count(
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    try:
        result = (
            supabase.table("user_notifications")
            .select("id", count="exact", head=True)
            .eq("user_id", user_id)
            .is_("read_at", "null")
            .execute()
        )

        return {"count": result.count or 0}

    except Exception as error:
        logger.error(
            "Notification unread count failed: %s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not load unread count",
        ) from None


@router.patch("/inbox/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    if notification_id < 1:
        raise HTTPException(
            status_code=400,
            detail="Invalid notification ID",
        )

    try:
        existing_result = (
            supabase.table("user_notifications")
            .select("id, read_at")
            .eq("id", notification_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not existing_result.data:
            raise HTTPException(
                status_code=404,
                detail="Notification not found",
            )

        existing = existing_result.data[0]

        if existing.get("read_at") is not None:
            return {
                "id": existing["id"],
                "read_at": existing["read_at"],
            }

        # 다른 요청이 먼저 읽음 처리했다면 시간을 덮어쓰지 않는다.
        updated_result = (
            supabase.table("user_notifications")
            .update({
                "read_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            })
            .eq("id", notification_id)
            .eq("user_id", user_id)
            .is_("read_at", "null")
            .execute()
        )

        if updated_result.data:
            updated = updated_result.data[0]

            return {
                "id": updated["id"],
                "read_at": updated["read_at"],
            }

        latest_result = (
            supabase.table("user_notifications")
            .select("id, read_at")
            .eq("id", notification_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not latest_result.data:
            raise HTTPException(
                status_code=404,
                detail="Notification not found",
            )

        return latest_result.data[0]

    except HTTPException:
        raise

    except Exception as error:
        logger.error(
            "Notification read update failed: %s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not mark notification as read",
        ) from None
