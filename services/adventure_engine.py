# services/adventure_engine.py
from datetime import datetime, timezone

REGION_DISTANCE = 18.0


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must include a timezone')
    return parsed.astimezone(timezone.utc)


def advance(distance, energy, updated_at, now):
    elapsed = max(0.0, (parse_time(now) - parse_time(updated_at)).total_seconds())
    return min(REGION_DISTANCE, max(0.0, float(distance)) + elapsed / 86400 * min(max(int(energy), 1), 3))


def public_state(row, now):
    distance = advance(row['distance'], row['energy'], row['updated_at'], now)
    return {
        'region': row['region'],
        'distance': round(distance, 6),
        'progress': round(distance / REGION_DISTANCE, 6),
        'arrived': distance >= REGION_DISTANCE,
        'startedAt': row['started_at'],
    }
