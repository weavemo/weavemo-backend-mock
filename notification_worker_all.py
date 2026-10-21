# notification_worker_all.py

import argparse
import time

from config.settings import settings
from db.database import get_supabase
from notification_worker import process_subscription
from services.push_sender import get_encoded_private_key


PAGE_SIZE = 100
CHECK_INTERVAL_SECONDS = 20


def run_cycle(dry_run: bool) -> None:
    supabase = get_supabase()

    # 이번 회차 시작 시점의 마지막 ID를 기준으로 조회한다.
    # 실행 도중 등록된 기기는 다음 회차에서 처리한다.
    latest_result = (
        supabase.table("push_subscriptions")
        .select("id")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if not latest_result.data:
        print("No registered devices.", flush=True)
        return

    max_id = latest_result.data[0]["id"]
    last_id = 0
    checked = 0
    errors = 0

    while last_id < max_id:
        result = (
            supabase.table("push_subscriptions")
            .select("id")
            .gt("id", last_id)
            .lte("id", max_id)
            .order("id")
            .limit(PAGE_SIZE)
            .execute()
        )

        rows = result.data or []

        if not rows:
            break

        for row in rows:
            subscription_id = row["id"]
            last_id = subscription_id
            checked += 1

            if dry_run:
                print(
                    f"Registered device: {subscription_id}",
                    flush=True,
                )
                continue

            try:
                # 각 기기의 사용자 시간대와 예약 시간을
                # 처리 시점에 조회하고 중복 발송을 막는다.
                process_subscription(subscription_id)
            except Exception as error:
                errors += 1

                # 한 기기 처리 실패가 나머지 기기를 막지 않는다.
                # 구독 주소나 비밀키는 출력하지 않는다.
                print(
                    f"Device {subscription_id} check failed: "
                    f"{type(error).__name__}",
                    flush=True,
                )

    print(
        f"Cycle completed. Devices={checked}, "
        f"Errors={errors}, DryRun={dry_run}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one check cycle and exit.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List registered device IDs without writing or sending.",
    )

    args = parser.parse_args()

    if not args.dry_run:
        if not settings.VAPID_SUBJECT:
            raise ValueError("VAPID_SUBJECT is missing")

        get_encoded_private_key()

    print(
        f"All-device worker started. DryRun={args.dry_run}",
        flush=True,
    )

    try:
        while True:
            started = time.monotonic()

            try:
                run_cycle(dry_run=args.dry_run)
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
            "\nAll-device worker stopped.",
            flush=True,
        )


if __name__ == "__main__":
    main()
