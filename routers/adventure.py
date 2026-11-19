# routers/adventure.py
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from db.database import get_supabase
from dependencies.auth import get_current_user
from services.adventure_engine import advance, parse_time, public_state, utc_now

router = APIRouter()


def latest_mood(db, user_id):
    result = (db.table('moods')
              .select('id,main_valence,energy,recorded_at')
              .eq('user_id', user_id)
              .order('recorded_at', desc=True)
              .order('id', desc=True)
              .limit(1).execute())
    return result.data[0] if result.data else None


def current_journey(db, user_id):
    result = (db.table('adventure_journeys').select('*')
              .eq('user_id', user_id).limit(1).execute())
    return result.data[0] if result.data else None


def direction_for(valence):
    # The emotion-to-direction relationship is intentionally not exposed.
    return {-2: 'west', -1: 'south', 0: 'north', 1: 'east', 2: 'northeast'}[int(valence)]


def settle_changes(db, user_id, row, now):
    """Replay mood changes at their actual timestamps, without skipping events."""
    for _ in range(3):
        start = parse_time(row['updated_at'])
        # Fetch one extra to detect an unsafe truncated history.
        response = (db.table('moods')
                    .select('id,energy,recorded_at')
                    .eq('user_id', user_id)
                    .gt('recorded_at', start.isoformat())
                    .lte('recorded_at', now.isoformat())
                    .order('recorded_at')
                    .order('id')
                    .limit(1001).execute())
        events = response.data or []
        if len(events) > 1000:
            raise HTTPException(503, 'Mood history is too large to settle safely')

        distance = float(row['distance'])
        energy = int(row['energy'])
        cursor = start
        last_id = row['last_mood_id']
        changed = False

        for event in events:
            when = parse_time(event['recorded_at'])
            if when < cursor:
                continue
            distance = advance(distance, energy, cursor, when)
            energy = int(event['energy'])
            cursor = when
            last_id = event['id']
            changed = True

        if not changed:
            return row

        distance = advance(distance, energy, cursor, now)
        changes = {
            'distance': distance,
            'energy': energy,
            'last_mood_id': last_id,
            'updated_at': now.isoformat(),
        }
        # Compare-and-swap protects against concurrent state reads.
        result = (db.table('adventure_journeys').update(changes)
                  .eq('user_id', user_id)
                  .eq('updated_at', row['updated_at'])
                  .eq('last_mood_id', row['last_mood_id'])
                  .execute())
        if result.data:
            return result.data[0]
        row = current_journey(db, user_id)
        if row is None:
            raise HTTPException(409, 'Journey was removed during update')

    raise HTTPException(409, 'Journey changed concurrently; retry')


@router.post('/start')
def start_journey(db=Depends(get_supabase), user=Depends(get_current_user)):
    user_id = int(user['user_id'])
    existing = current_journey(db, user_id)
    if existing:
        now = utc_now()
        return public_state(settle_changes(db, user_id, existing, now), now)

    mood = latest_mood(db, user_id)
    if not mood:
        raise HTTPException(409, 'Mood check-in required before departure')

    now = utc_now()
    row = {
        'user_id': user_id,
        'region': 1,
        'distance': 0,
        'direction': direction_for(mood['main_valence']),
        'energy': mood['energy'],
        'last_mood_id': mood['id'],
        'started_at': now.isoformat(),
        'updated_at': now.isoformat(),
    }
    db.table('adventure_journeys').upsert(
        row, on_conflict='user_id', ignore_duplicates=True
    ).execute()
    stored = current_journey(db, user_id)
    if not stored:
        raise HTTPException(503, 'Journey could not be loaded')
    return public_state(stored, utc_now())


@router.get('/state')
def get_journey_state(db=Depends(get_supabase), user=Depends(get_current_user)):
    user_id = int(user['user_id'])
    row = current_journey(db, user_id)
    if row is None:
        return None
    now = utc_now()
    return public_state(settle_changes(db, user_id, row, now), now)
