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
