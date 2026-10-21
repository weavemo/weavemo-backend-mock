# services/push_sender.py

import base64
import json
from functools import lru_cache
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import webpush, WebPushException

from config.settings import settings


@lru_cache(maxsize=1)
def get_encoded_private_key() -> str:
    raw_key = settings.VAPID_PRIVATE_KEY.strip()

    if not raw_key:
        raise ValueError("VAPID private key is missing")

    key_bytes = base64.urlsafe_b64decode(
        raw_key + "=" * (-len(raw_key) % 4)
    )

    if len(key_bytes) != 32:
        raise ValueError("Invalid VAPID private key")

    private_key = ec.derive_private_key(
        int.from_bytes(key_bytes, "big"),
        ec.SECP256R1(),
    )

    der_key = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return base64.urlsafe_b64encode(
        der_key
    ).rstrip(b"=").decode("ascii")


def get_reminder_payload(
    kind: str,
    locale: str,
    local_date: str,
) -> dict:
    if kind not in ("morning", "evening"):
        raise ValueError("Invalid notification kind")

    is_korean = locale.lower().startswith("ko")

    if kind == "morning":
        body = (
            "오늘 마음은 어떤가요? 잠깐 나를 살펴보세요."
            if is_korean
            else "How are you feeling today? Take a moment for yourself."
        )
    else:
        body = (
            "오늘 하루는 어땠나요? 나를 위한 작은 기록을 남겨보세요."
            if is_korean
            else "How was your day? Take a moment to reflect."
        )

    return {
        "title": "WeaveMo",
        "body": body,
        "url": "/home",
        "tag": f"weavemo-{kind}-{local_date}",
    }


def send_push(
    subscription: dict,
    payload: dict,
) -> tuple[str, int | None]:
    if (
        not settings.VAPID_PRIVATE_KEY
        or not settings.VAPID_SUBJECT
    ):
        raise ValueError("Web Push configuration is missing")

    endpoint = subscription["endpoint"]

    try:
        parsed = urlsplit(endpoint)

        # 현재 검증한 Chrome 푸시 서비스만 허용한다.
        # 다른 브라우저 제공자는 별도 검증 후 추가한다.
        valid_endpoint = (
            parsed.scheme == "https"
            and parsed.hostname == "fcm.googleapis.com"
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
        )
    except ValueError:
        valid_endpoint = False

    if not valid_endpoint:
        return "failed", None

    try:
        response = webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {
                    "p256dh": subscription["p256dh"],
                    "auth": subscription["auth"],
                },
            },
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=get_encoded_private_key(),
            vapid_claims={
                "sub": settings.VAPID_SUBJECT,
            },
            ttl=120,
            timeout=15,
        )

        # accepted는 푸시 서비스 접수이며 실제 열람 확인은 아니다.
        if 200 <= response.status_code < 300:
            return "accepted", response.status_code

        return "failed", response.status_code

    except WebPushException as error:
        status = (
            error.response.status_code
            if error.response is not None
            else None
        )

        if status in (404, 410):
            return "expired", status

        return "failed", status

    except Exception:
        # 구독 주소나 비밀키를 오류 출력에 포함하지 않는다.
        return "failed", None
