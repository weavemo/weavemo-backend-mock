# services/notification_schedule.py

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# 예약 시각부터 2분 이내에만 발송 대상으로 판단한다.
# 서버를 오래 껐다 켰을 때 지난 알림이 몰아서 나가지 않게 한다.
DELIVERY_WINDOW_SECONDS = 120


def get_due_notifications(
    user: dict,
    now_utc: datetime | None = None,
) -> list[dict]:
    timezone_name = user.get("notification_timezone")

    # 시간대를 아직 저장하지 않은 사용자는 발송하지 않는다.
    if not timezone_name:
        return []

    try:
        user_timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return []

    now = now_utc or datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError("now_utc must include timezone")

    now = now.astimezone(timezone.utc)
    local_today = now.astimezone(user_timezone).date()

    due = []

    for kind, column in (
        ("morning", "notif_time_am"),
        ("evening", "notif_time_pm"),
    ):
        raw_time = user.get(column)

        if not raw_time:
            continue

        try:
            scheduled_time = time.fromisoformat(
                str(raw_time)
            )
        except ValueError:
            continue

        if scheduled_time.tzinfo is not None:
            continue

        # 자정 직전 예약도 2분의 발송 허용 시간을 적용한다.
        for local_date in (
            local_today - timedelta(days=1),
            local_today,
        ):
            local_naive = datetime.combine(
                local_date,
                scheduled_time,
            )

            # 서머타임 종료로 같은 시간이 두 번 생기면
            # 첫 번째 시각을 기준으로 한다.
            local_scheduled = local_naive.replace(
                tzinfo=user_timezone,
                fold=0,
            )

            scheduled_utc = local_scheduled.astimezone(
                timezone.utc
            )

            # 서머타임 시작으로 존재하지 않는 시각은 건너뛴다.
            round_trip = scheduled_utc.astimezone(
                user_timezone
            ).replace(tzinfo=None)

            if round_trip != local_naive:
                continue

            elapsed = (now - scheduled_utc).total_seconds()

            if 0 <= elapsed < DELIVERY_WINDOW_SECONDS:
                due.append({
                    "notification_kind": kind,
                    "local_date": local_date.isoformat(),
                    "scheduled_at": scheduled_utc.isoformat(),
                })

    return due
