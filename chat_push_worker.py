# weavemo-backend-mock/chat_push_worker.py

import argparse
import time
from datetime import datetime, timezone

from config.settings import settings
from db.database import get_supabase
from services.push_sender import (
    get_chat_payload,
    get_encoded_private_key,
    send_push,
)

PAGE_SIZE = 100
CHECK_INTERVAL_SECONDS = 2


def run_cycle(dry_run: bool) -> int:
    supabase = get_supabase()

    result = (
        supabase.table("chat_push_deliveries")
        .select("id")
        .eq("status", "pending")
        .lte(
            "available_at",
            datetime.now(timezone.utc).isoformat(),
        )
        .order("id")
        .limit(PAGE_SIZE)
        .execute()
    )

    deliveries = result.data or []

    if dry_run:
        print(
            f"Chat push check: Pending={len(deliveries)}, "
            "DryRun=True",
            flush=True,
        )
        return 0

    errors = 0

    for delivery in deliveries:
        delivery_id = delivery["id"]

        try:
            claim = supabase.rpc(
                "weavemo_claim_chat_push",
                {"p_delivery_id": delivery_id},
            ).execute()

            data = claim.data

            if (
                not isinstance(data, dict)
                or not isinstance(data.get("send"), bool)
            ):
                raise ValueError("Invalid claim response")

            if not data["send"]:
                continue

        except Exception as error:
            errors += 1
            print(
                f"Chat push {delivery_id}: claim failed "
                f"({type(error).__name__})",
                flush=True,
            )
            continue

        subscription = data.get("subscription")
        status = "failed"
        http_status = None

        try:
            if not isinstance(subscription, dict):
                raise ValueError("Invalid subscription")

            payload = get_chat_payload(
                kind=data["kind"],
                locale=data["locale"],
                sender_name=data["sender_name"],
                sender_id=int(data["sender_id"]),
                conversation_id=int(data["conversation_id"]),
            )

            status, http_status = send_push(
                subscription,
                payload,
            )

        except Exception as error:
            errors += 1
            print(
                f"Chat push {delivery_id}: send failed "
                f"({type(error).__name__})",
                flush=True,
            )

        try:
            (
                supabase.table("chat_push_deliveries")
                .update({
                    "status": status,
                    "http_status": http_status,
                    "finished_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                })
                .eq("id", delivery_id)
                .eq("status", "claimed")
                .execute()
            )

        except Exception as error:
            errors += 1
            print(
                f"Chat push {delivery_id}: result save failed "
                f"({type(error).__name__})",
                flush=True,
            )

        print(
            f"Chat push {delivery_id}: "
            f"{status} HTTP={http_status}",
            flush=True,
        )

        if status == "expired" and isinstance(subscription, dict):
            try:
                (
                    supabase.table("push_subscriptions")
                    .delete()
                    .eq("id", subscription["id"])
                    .eq("user_id", data["recipient_id"])
                    .eq("endpoint", subscription["endpoint"])
                    .execute()
                )

            except Exception as error:
                errors += 1
                print(
                    "Expired chat subscription cleanup failed: "
                    f"{type(error).__name__}",
                    flush=True,
                )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--once",
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    args = parser.parse_args()

    if not args.dry_run:
        if not settings.VAPID_SUBJECT:
            raise ValueError("VAPID_SUBJECT is missing")

        get_encoded_private_key()

    print(
        f"Chat push worker started. DryRun={args.dry_run}",
        flush=True,
    )

    try:
        while True:
            started = time.monotonic()
            errors = 0

            try:
                errors = run_cycle(args.dry_run)
            except Exception as error:
                errors = 1
                print(
                    "Chat push cycle failed: "
                    f"{type(error).__name__}",
                    flush=True,
                )

            if args.once:
                raise SystemExit(1 if errors else 0)

            elapsed = time.monotonic() - started
            time.sleep(
                max(0.5, CHECK_INTERVAL_SECONDS - elapsed)
            )

    except KeyboardInterrupt:
        print(
            "\nChat push worker stopped.",
            flush=True,
        )


if __name__ == "__main__":
    main()
