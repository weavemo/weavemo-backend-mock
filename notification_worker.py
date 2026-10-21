# notification_worker.py

import argparse
import time
from datetime import datetime, timezone

from config.settings import settings
from db.database import get_supabase
from services.notification_schedule import get_due_notifications
from services.push_sender import (
    get_encoded_private_key,
    get_reminder_payload,
    send_push,
)


def process_subscription(subscription_id: int) -> None:
    supabase = get_supabase()

    subscription_result = (
        supabase.table("push_subscriptions")
        .select("id, user_id, endpoint, p256dh, auth")
        .eq("id", subscription_id)
        .limit(1)
        .execute()
    )

    if not subscription_result.data:
        print("Subscription not found.", flush=True)
        return

    subscription = subscription_result.data[0]

    user_result = (
        supabase.table("users")
        .select(
            "id, locale, notification_timezone, "
            "notif_time_am, notif_time_pm"
        )
        .eq("id", subscription["user_id"])
        .limit(1)
        .execute()
    )

    if not user_result.data:
        print("User not found.", flush=True)
        return

    user = user_result.data[0]
    due_notifications = get_due_notifications(user)

    for due in due_notifications:
        # 여러 실행 프로세스가 있어도 DB 고유 제약으로
        # 같은 날짜·종류·기기의 발송 권한은 한 번만 확보한다.
        try:
            claim_result = (
                supabase.table("notification_deliveries")
                .insert({
                    "subscription_id": subscription["id"],
                    "local_date": due["local_date"],
                    "notification_kind": due[
                        "notification_kind"
                    ],
                    "status": "claimed",
                })
                .execute()
            )
        except Exception as error:
            if str(getattr(error, "code", "")) == "23505":
                # 이미 처리한 알림이므로 다시 보내지 않는다.
                continue

            print(
                "Delivery claim failed:",
                type(error).__name__,
                flush=True,
            )
            continue

        if not claim_result.data:
            # 기록 확보를 확인하지 못하면 발송하지 않는다.
            print("Delivery claim was not confirmed.", flush=True)
            continue

        delivery_id = claim_result.data[0]["id"]

        try:
            payload = get_reminder_payload(
                kind=due["notification_kind"],
                locale=user.get("locale") or "ko-KR",
                local_date=due["local_date"],
            )

            status, http_status = send_push(
                subscription,
                payload,
            )
        except Exception as error:
            status = "failed"
            http_status = None

            print(
                "Delivery failed:",
                type(error).__name__,
                flush=True,
            )

        try:
            (
                supabase.table("notification_deliveries")
                .update({
                    "status": status,
                    "http_status": http_status,
                    "finished_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                })
                .eq("id", delivery_id)
                .execute()
            )
        except Exception as error:
            # 결과 저장 실패 시 claimed 기록을 유지한다.
            # 접수됐을 수 있는 알림을 중복 발송하지 않는다.
            print(
                "Delivery result save failed:",
                type(error).__name__,
                flush=True,
            )

        print(
            f"Delivery {delivery_id}: "
            f"{due['notification_kind']} "
            f"{status} HTTP={http_status}",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--subscription-id",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--once",
        action="store_true",
    )
    args = parser.parse_args()

    if args.subscription_id < 1:
        parser.error("subscription-id must be positive")

    if not settings.VAPID_SUBJECT:
        raise ValueError("VAPID_SUBJECT is missing")

    # 실행 전에 키 설정을 검사한다.
    get_encoded_private_key()

    print(
        f"Notification worker started. "
        f"Subscription={args.subscription_id}",
        flush=True,
    )

    try:
        while True:
            started = time.monotonic()

            try:
                process_subscription(args.subscription_id)
            except Exception as error:
                print(
                    "Notification cycle failed:",
                    type(error).__name__,
                    flush=True,
                )

            if args.once:
                print("Notification check completed.", flush=True)
                break

            # 한 번의 조회가 느려져도 실행이 겹치지 않는다.
            elapsed = time.monotonic() - started
            time.sleep(max(1, 20 - elapsed))

    except KeyboardInterrupt:
        print("\nNotification worker stopped.", flush=True)


if __name__ == "__main__":
    main()
