# weavemo-backend-mock/chat_cleanup_worker.py

import argparse
import time

from db.database import get_supabase

PAGE_SIZE = 100
CHECK_INTERVAL_SECONDS = 20


def run_cycle(dry_run: bool) -> int:
    supabase = get_supabase()

    latest = (
        supabase.table("chat_conversations")
        .select("id")
        .eq("kind", "direct")
        .eq("invitation_status", "accepted")
        .is_("ended_at", "null")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if not latest.data:
        print(
            f"Chat cycle completed. Checked=0, Ended=0, "
            f"WouldEnd=0, Errors=0, DryRun={dry_run}",
            flush=True,
        )
        return 0

    max_id = latest.data[0]["id"]
    last_id = 0
    checked = 0
    ended = 0
    would_end = 0
    errors = 0

    while last_id < max_id:
        result = (
            supabase.table("chat_conversations")
            .select("id")
            .eq("kind", "direct")
            .eq("invitation_status", "accepted")
            .is_("ended_at", "null")
            .gt("id", last_id)
            .lte("id", max_id)
            .order("id")
            .limit(PAGE_SIZE)
            .execute()
        )

        rooms = result.data or []

        if not rooms:
            break

        for room in rooms:
            room_id = room["id"]
            last_id = room_id
            checked += 1

            try:
                response = supabase.rpc(
                    "weavemo_expire_chat",
                    {
                        "p_conversation_id": room_id,
                        "p_dry_run": dry_run,
                    },
                ).execute()

                data = response.data

                if (
                    not isinstance(data, dict)
                    or data.get("error")
                    or not isinstance(data.get("expired"), bool)
                    or not isinstance(data.get("ended"), bool)
                    or data.get("status") not in {
                        "not_found",
                        "skipped",
                        "active",
                        "would_end",
                        "ended",
                    }
                ):
                    raise ValueError("Invalid expiry response")

                if data["ended"]:
                    ended += 1
                    print(
                        f"Chat {room_id}: ended after "
                        "3 minutes without a connection signal.",
                        flush=True,
                    )
                elif data["status"] == "would_end":
                    would_end += 1
                    print(
                        f"Chat {room_id}: would end. DryRun=True",
                        flush=True,
                    )

            except Exception as error:
                errors += 1
                print(
                    f"Chat {room_id} cleanup failed: "
                    f"{type(error).__name__}: {error}",
                    flush=True,
                )

    print(
        f"Chat cycle completed. Checked={checked}, "
        f"Ended={ended}, WouldEnd={would_end}, "
        f"Errors={errors}, DryRun={dry_run}",
        flush=True,
    )

    return errors


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
        help="Check expiry without ending conversations.",
    )

    args = parser.parse_args()

    print(
        f"Chat cleanup worker started. DryRun={args.dry_run}",
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
                    "Chat cleanup cycle failed: "
                    f"{type(error).__name__}: {error}",
                    flush=True,
                )

            if args.once:
                raise SystemExit(1 if errors else 0)

            elapsed = time.monotonic() - started

            time.sleep(
                max(1, CHECK_INTERVAL_SECONDS - elapsed)
            )

    except KeyboardInterrupt:
        print(
            "\nChat cleanup worker stopped.",
            flush=True,
        )


if __name__ == "__main__":
    main()
