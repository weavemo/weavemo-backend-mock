# notification_worker_all.py

import argparse
import time

from config.settings import settings
from db.database import get_supabase
from notification_worker import (
    process_subscription,
    save_inbox_notification,
)
from services.notification_schedule import get_due_notifications
from services.push_sender import (
    get_encoded_private_key,
    get_reminder_payload,
)


PAGE_SIZE = 100
CHECK_INTERVAL_SECONDS = 20


def process_user(
    supabase,
    user: dict,
    push_enabled: bool,
) -> None:
    due_notifications = get_due_notifications(user)

    if not due_notifications:
        return

    inbox_ready = False

    for due in due_notifications:
        payload = get_reminder_payload(
            kind=due["notification_kind"],
            locale=user.get("locale") or "ko-KR",
            local_date=due["local_date"],
        )

        saved = save_inbox_notification(
            supabase,
            user["id"],
            due,
            payload,
        )

        if saved:
            inbox_ready = True

    if not inbox_ready or not push_enabled:
        return

    # 기기 등록이 없어도 위의 알림함 저장은 완료된다.
    # 기기는 ID 순서로 나눠 조회해 누락을 피한다.
    last_subscription_id = 0

    latest = (
        supabase.table("push_subscriptions")
        .select("id")
        .eq("user_id", user["id"])
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if not latest.data:
        return

    max_subscription_id = latest.data[0]["id"]

    while last_subscription_id < max_subscription_id:
        result = (
            supabase.table("push_subscriptions")
            .select("id")
            .eq("user_id", user["id"])
            .gt("id", last_subscription_id)
            .lte("id", max_subscription_id)
            .order("id")
            .limit(PAGE_SIZE)
            .execute()
        )

        subscriptions = result.data or []

        if not subscriptions:
            break

        for subscription in subscriptions:
            last_subscription_id = subscription["id"]

            try:
                # 기존 함수가 최신 예약과 기기 상태를 재확인한다.
                # 알림함의 고유 제약으로 중복 기록은 생기지 않는다.
                # 푸시 중복 방지와 만료 기기 정리도 그대로 사용한다.
                process_subscription(subscription["id"])
            except Exception as error:
                print(
                    f"Device {subscription['id']} failed: "
                    f"{type(error).__name__}",
                    flush=True,
                )


def run_cycle(
    dry_run: bool,
    push_enabled: bool,
) -> None:
    supabase = get_supabase()

    latest = (
        supabase.table("users")
        .select("id")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if not latest.data:
        print("No users found.", flush=True)
        return

    max_user_id = latest.data[0]["id"]
    last_user_id = 0
    checked = 0
    errors = 0

    while last_user_id < max_user_id:
        result = (
            supabase.table("users")
            .select(
                "id, locale, notification_timezone, "
                "notif_time_am, notif_time_pm"
            )
            .gt("id", last_user_id)
            .lte("id", max_user_id)
            .order("id")
            .limit(PAGE_SIZE)
            .execute()
        )

        users = result.data or []

        if not users:
            break

        for user in users:
            last_user_id = user["id"]
            checked += 1

            if dry_run:
                due = get_due_notifications(user)

                print(
                    f"User {user['id']}: Due={len(due)}",
                    flush=True,
                )
                continue

            try:
                process_user(
                    supabase,
                    user,
                    push_enabled,
                )
            except Exception as error:
                errors += 1

                print(
                    f"User {user['id']} failed: "
                    f"{type(error).__name__}",
                    flush=True,
                )

    print(
        f"Cycle completed. Users={checked}, "
        f"UserErrors={errors}, DryRun={dry_run}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one cycle and exit.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check schedules without writing or sending.",
    )

    args = parser.parse_args()

    push_enabled = False

    if not args.dry_run:
        try:
            if not settings.VAPID_SUBJECT:
                raise ValueError("VAPID_SUBJECT is missing")

            get_encoded_private_key()
            push_enabled = True
        except Exception as error:
            # 푸시 설정 문제로 알림함 생성까지 멈추지 않는다.
            print(
                "Push unavailable; inbox processing continues:",
                type(error).__name__,
                flush=True,
            )

    print(
        f"User notification worker started. "
        f"DryRun={args.dry_run}, PushEnabled={push_enabled}",
        flush=True,
    )

    try:
        while True:
            started = time.monotonic()

            try:
                run_cycle(
                    dry_run=args.dry_run,
                    push_enabled=push_enabled,
                )
            except Exception as error:
                print(
                    "Notification cycle failed:",
                    type(error).__name__,
                    flush=True,
                )

            if args.once:
                break

            elapsed = time.monotonic() - started

            if elapsed >= 120:
                print(
                    "Warning: cycle exceeded the "
                    "2-minute delivery window.",
                    flush=True,
                )

            time.sleep(
                max(1, CHECK_INTERVAL_SECONDS - elapsed)
            )

    except KeyboardInterrupt:
        print(
            "\nNotification worker stopped.",
            flush=True,
        )


if __name__ == "__main__":
    main()
