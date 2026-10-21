# test_push.py

import base64
import json
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import webpush, WebPushException

from config.settings import settings
from db.database import get_supabase


SUBSCRIPTION_ID = 1


def main():
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_SUBJECT:
        print("Missing VAPID key or contact configuration.")
        return

    result = (
        get_supabase()
        .table("push_subscriptions")
        .select("id, endpoint, p256dh, auth")
        .eq("id", SUBSCRIPTION_ID)
        .limit(1)
        .execute()
    )

    if not result.data:
        print("Subscription 1 not found. Enable notifications again.")
        return

    subscription = result.data[0]
    endpoint = subscription["endpoint"]
    parsed = urlsplit(endpoint)

    # 이번 테스트는 Chrome의 Google 푸시 서비스만 대상으로 한다.
    if (
        parsed.scheme != "https"
        or parsed.hostname != "fcm.googleapis.com"
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        print("Unexpected push provider. Test stopped.")
        return

    # 저장된 32바이트 개인키를 라이브러리용 DER 형식으로 변환한다.
    raw_key = settings.VAPID_PRIVATE_KEY.strip()
    key_bytes = base64.urlsafe_b64decode(
        raw_key + "=" * (-len(raw_key) % 4)
    )

    if len(key_bytes) != 32:
        print("Invalid private key format.")
        return

    private_key = ec.derive_private_key(
        int.from_bytes(key_bytes, "big"),
        ec.SECP256R1(),
    )

    der_key = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    encoded_key = base64.urlsafe_b64encode(
        der_key
    ).rstrip(b"=").decode("ascii")

    payload = {
        "title": "WeaveMo",
        "body": "테스트 알림이 도착했어요. 마음을 위한 작은 순간이에요.",
        "url": "/home",
        "tag": "weavemo-test",
    }

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
            vapid_private_key=encoded_key,
            vapid_claims={
                "sub": settings.VAPID_SUBJECT,
            },
            ttl=60,
            timeout=15,
        )

        print(
            "Push service accepted:",
            response.status_code,
        )
        print("Check the browser or Windows notification center.")

    except WebPushException as error:
        status = (
            error.response.status_code
            if error.response is not None
            else "No HTTP response"
        )
        print("Push failed. Status:", status)

    except Exception as error:
        print("Push failed. Error type:", type(error).__name__)


if __name__ == "__main__":
    main()
