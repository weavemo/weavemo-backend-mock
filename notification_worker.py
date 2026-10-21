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


def save_inbox_notification(
    supabase,
    user_id: int,
    due: dict,
    payload: dict,
) -> bool:
    try:
        (
            supabase.table("user_notifications")
            .insert({
                "user_id": user_id,
                "kind": due["notification_kind"],
                "local_date": due["local_date"],
                "title": payload["title"],
                "body": payload["body"],
                "target_path": payload["url"],
            })
            .execute()
        )

        print(
            f"Inbox saved: "
            f"{due['notification_kind']} "
            f"{due['local_date']}",
            flush=True,
        )
        return True

    except Exception as error:
        if str(getattr(error, "code", "")) == "23505":
            # 다른 기기 또는 이전 실행에서 이미 저장한 알림이다.
            # 읽음 상태를 보존하기 위해 덮어쓰지 않는다.
            return True

        print(
            "Inbox save failed:",
            type(error).__name__,
            flush=True,
        )
        return False


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
        payload = get_reminder_payload(
            kind=due["notification_kind"],
            locale=user.get("locale") or "ko-KR",
            local_date=due["local_date"],
        )

        # 푸시 발송 여부와 별개로 알림함에 먼저 저장한다.
        # 저장 실패 시 이번 회차에서는 보내지 않고,
        # 다음 회차에서 예약 허용 시간 안에 다시 시도한다.
        inbox_saved = save_inbox_notification(
            supabase,
            user["id"],
            due,
            payload,
        )

        if not inbox_saved:
            continue

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
                # 오늘 이 기기에 이미 시도한 종류는 다시 보내지 않는다.
                continue

            print(
                "Delivery claim failed:",
                type(error).__name__,
                flush=True,
            )
            continue

        if not claim_result.data:
            print(
                "Delivery claim was not confirmed.",
                flush=True,
            )
            continue

        delivery_id = claim_result.data[0]["id"]

        try:
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
            # 접수됐을 수 있는 알림은 다시 보내지 않는다.
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

        if status == "expired":
            try:
                (
                    supabase.table("push_subscriptions")
                    .delete()
                    .eq("id", subscription["id"])
                    .eq("user_id", subscription["user_id"])
                    .execute()
                )

                print(
                    f"Expired subscription removed: "
                    f"{subscription['id']}",
                    flush=True,
                )

                return

            except Exception as error:
                print(
                    "Expired subscription cleanup failed:",
                    type(error).__name__,
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
                process_subscription(
                    args.subscription_id
                )
            except Exception as error:
                print(
                    "Notification cycle failed:",
                    type(error).__name__,
                    flush=True,
                )

            if args.once:
                print(
                    "Notification check completed.",
                    flush=True,
                )
                break

            elapsed = time.monotonic() - started
            time.sleep(max(1, 20 - elapsed))

    except KeyboardInterrupt:
        print(
            "\nNotification worker stopped.",
            flush=True,
        )


if __name__ == "__main__":
    main()
