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
# weavemo-backend-mock/services/push_sender.py
# 기존 코드 맨 아래에 추가

def get_chat_payload(
    kind: str,
    locale: str,
    sender_name: str,
    sender_id: int,
    conversation_id: int,
) -> dict:
    if kind not in ("invitation", "message"):
        raise ValueError("Invalid chat notification kind")

    is_korean = locale.lower().startswith("ko")

    nickname = (sender_name or "").strip()[:80]

    if not nickname:
        nickname = "친구" if is_korean else "Your friend"

    if kind == "invitation":
        body = (
            f"{nickname}님이 대화를 요청했어요."
            if is_korean
            else f"{nickname} would like to chat."
        )

        # 홈에서 기존 요청 모달로 수락·거절한다.
        target_path = "/home"
    else:
        body = (
            f"{nickname}님에게 새 메시지가 왔어요."
            if is_korean
            else f"You have a new message from {nickname}."
        )

        target_path = (
            f"/chat/with/{int(sender_id)}"
            f"?room={int(conversation_id)}"
        )

    return {
        "title": "WeaveMo",
        "body": body,
        "url": target_path,
        "tag": f"weavemo-chat-{int(conversation_id)}",
    }
# weavemo-backend-mock/services/push_sender.py
# 기존 코드 맨 아래에 추가

def get_note_payload(
    kind: str,
    locale: str,
    sender_name: str,
    note_id: int,
) -> dict:
    if kind not in ("note", "request"):
        raise ValueError("Invalid note notification kind")

    is_korean = (locale or "").lower().startswith("ko")
    nickname = (sender_name or "").strip()[:80]

    if not nickname:
        nickname = "누군가" if is_korean else "Someone"

    if kind == "request":
        body = (
            f"{nickname}님이 쪽지 요청을 보냈어요."
            if is_korean
            else f"{nickname} sent you a note request."
        )
    else:
        body = (
            f"{nickname}님이 쪽지를 보냈어요."
            if is_korean
            else f"{nickname} sent you a note."
        )

    return {
        "title": "WeaveMo",
        "body": body,
        "url": "/notes",
        "tag": f"weavemo-note-{int(note_id)}",
    }
# weavemo-backend-mock/services/push_sender.py
# 기존 코드 맨 아래에 추가

def get_moderation_payload(
    kind: str,
    locale: str,
    event_id: int,
) -> dict:
    is_korean = (locale or "").lower().startswith("ko")

    messages = {
        "admin_report": (
            "새 신고가 접수됐어요. 신고 관리에서 확인해 주세요.",
            "A new report was submitted. Open report management to review it.",
        ),
        "moderation_warning": (
            "운영자 경고가 도착했어요. 앱에서 내용을 확인해 주세요.",
            "You received a moderator warning. Open the app to review it.",
        ),
        "moderation_restriction": (
            "쪽지·채팅 전송이 일시 제한됐어요. 앱에서 사유와 종료 시각을 확인해 주세요.",
            "Messaging is temporarily restricted. Open the app for the reason and end time.",
        ),
        "moderation_revoked": (
            "전송 제한 한 건이 해제됐어요. 앱에서 현재 상태를 확인해 주세요.",
            "A messaging restriction was lifted. Open the app to check your current status.",
        ),
    }

    if kind not in messages or event_id < 1:
        raise ValueError("Invalid moderation notification")

    korean, english = messages[kind]

    return {
        "title": "WeaveMo",
        "body": korean if is_korean else english,
        "url": (
            "/admin/note-reports"
            if kind == "admin_report"
            else "/notes"
        ),
        "tag": f"weavemo-{kind}-{event_id}",
    }
