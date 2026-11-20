# routers/adventure.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from db.database import get_supabase
from dependencies.auth import get_current_user
from services.adventure_engine import advance, public_state, utc_now, parse_time

router = APIRouter()
GATE_MINUTES = (5, 8, 10, 15, 20)
COOLDOWN = timedelta(hours=8)


def latest_mood(db, user_id):
    response = (db.table('moods').select('id,main_valence,energy,recorded_at')
                .eq('user_id', user_id).order('recorded_at', desc=True)
                .order('id', desc=True).limit(1).execute())
    return response.data[0] if response.data else None


def current_journey(db, user_id):
    response = (db.table('adventure_journeys').select('*').eq('user_id', user_id)
                .limit(1).execute())
    return response.data[0] if response.data else None


def direction_for(valence):
    # Keep the emotional direction mapping private.
    return {-2: 'west', -1: 'south', 0: 'north', 1: 'east', 2: 'northeast'}[int(valence)]




def settle_journey(db, user_id, now=None):
    """Persist travel only up to the next unsolved checkpoint.

    The timestamp is rebased when a checkpoint is reached so that time spent
    reading a letter or solving a puzzle never becomes retroactive travel.
    """
    now = now or utc_now()
    for _ in range(3):
        row = current_journey(db, user_id)
        if not row:
            return None
        region = int(row['region'])
        progress = (db.table('adventure_puzzle_progress').select('gate,status')
                    .eq('user_id', user_id).eq('region', region).execute()).data or []
        done = {int(item['gate']) for item in progress if item['status'] == 'completed'}
        next_gate = next((gate for gate in range(1, 6) if gate not in done), None)
        ceiling = float(next_gate * 3 if next_gate else 18)
        distance = min(float(row['distance']), ceiling)
        cursor = parse_time(row['updated_at'])
        energy = row['energy']
        last_mood_id = row['last_mood_id']
        if distance < ceiling and cursor < now:
            changes = (db.table('moods').select('id,energy,recorded_at')
                       .eq('user_id', user_id).gt('recorded_at', cursor.isoformat())
                       .lte('recorded_at', now.isoformat())
                       .order('recorded_at').order('id').execute()).data or []
            for change in changes:
                change_time = parse_time(change['recorded_at'])
                if change_time < cursor:
                    continue
                distance = min(ceiling, advance(distance, energy, cursor, change_time))
                cursor = change_time
                energy = change['energy']
                last_mood_id = change['id']
                if distance >= ceiling:
                    break
            if distance < ceiling:
                distance = min(ceiling, advance(distance, energy, cursor, now))
        # Once a checkpoint is reached, rebase the clock and freeze there.
        # Keep the latest energy ready for travel after puzzle completion.
        if distance >= ceiling:
            mood = latest_mood(db, user_id)
            if mood:
                energy = mood['energy']
                last_mood_id = mood['id']
        if (abs(distance - float(row['distance'])) < 1e-9
                and str(energy) == str(row['energy'])
                and str(last_mood_id) == str(row['last_mood_id'])
                and cursor >= now):
            return row
        updated = (db.table('adventure_journeys').update({
            'distance': distance, 'energy': energy,
            'last_mood_id': last_mood_id, 'updated_at': now.isoformat(),
        }).eq('user_id', user_id).eq('updated_at', row['updated_at']).execute())
        if updated.data:
            return updated.data[0]
    return current_journey(db, user_id)


def journey_public_state(db, user_id, now=None):
    now = now or utc_now()
    row = settle_journey(db, user_id, now)
    if not row:
        return None
    distance = min(18.0, float(row['distance']))
    return {'region': row['region'], 'distance': round(distance, 6),
            'progress': round(distance / 18.0, 6), 'arrived': distance >= 18,
            'startedAt': row['started_at']}

@router.post('/start')
def start_journey(db=Depends(get_supabase), user=Depends(get_current_user)):
    user_id = int(user['user_id'])
    existing = current_journey(db, user_id)
    if existing:
        return journey_public_state(db, user_id)
    mood = latest_mood(db, user_id)
    if not mood:
        raise HTTPException(status_code=409, detail='Mood check-in required before departure')
    now = utc_now().isoformat()
    row = {'user_id': user_id, 'region': 1, 'distance': 0,
           'direction': direction_for(mood['main_valence']),
           'energy': mood['energy'], 'last_mood_id': mood['id'],
           'started_at': now, 'updated_at': now}
    # SQL checks energy/readiness and creates the journey under the SAME user lock.
    result = db.rpc('depart_companion_v1', {'p_user_id': user_id, 'p_journey': row}).execute().data
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise HTTPException(status_code=409, detail='Companion is not ready for departure')
    stored = current_journey(db, user_id)
    if not stored:
        raise HTTPException(status_code=503, detail='Journey could not be loaded')
    return journey_public_state(db, user_id)


@router.get('/state')
def get_journey_state(db=Depends(get_supabase), user=Depends(get_current_user)):
    return journey_public_state(db, int(user['user_id']))


def gate_row(db, user_id, region, gate):
    result = (db.table('adventure_puzzle_progress').select('*')
              .eq('user_id', user_id).eq('region', region).eq('gate', gate)
              .limit(1).execute())
    return result.data[0] if result.data else None


def validate_gate(region, gate):
    if not (1 <= region <= 8 and 1 <= gate <= 5):
        raise HTTPException(status_code=404, detail='Unknown gate')


def settle_expiry(db, row, now):
    if row and row['status'] == 'playing' and row.get('deadline_at') and parse_time(row['deadline_at']) <= now:
        until = parse_time(row['deadline_at']) + COOLDOWN
        result = (db.table('adventure_puzzle_progress')
                  .update({'status': 'cooldown', 'cooldown_until': until.isoformat()})
                  .eq('user_id', row['user_id']).eq('region', row['region'])
                  .eq('gate', row['gate']).eq('status', 'playing')
                  .eq('deadline_at', row['deadline_at']).execute())
        return result.data[0] if result.data else gate_row(db, row['user_id'], row['region'], row['gate'])
    return row


def public_gate(row, region, gate, now):
    status = row['status'] if row else 'pending'
    if status == 'cooldown' and row.get('cooldown_until') and parse_time(row['cooldown_until']) <= now:
        status = 'retry_ready'
    return {'region': region, 'gate': gate, 'status': status,
            'limitSeconds': GATE_MINUTES[gate - 1] * 60,
            'deadlineAt': row.get('deadline_at') if status == 'playing' else None,
            'cooldownUntil': row.get('cooldown_until') if status == 'cooldown' else None,
            'completedAt': row.get('completed_at') if row else None,
            'attemptCount': row.get('attempt_count', 0) if row else 0,
            'serverNow': now.isoformat()}


def gate_available(db, user_id, region, gate, now):
    journey = settle_journey(db, user_id, now)
    if not journey or int(journey['region']) != region:
        raise HTTPException(status_code=409, detail='Journey is not in this region')
    distance = float(journey['distance'])
    if distance < gate * 3:
        raise HTTPException(status_code=409, detail='Gate has not been reached')
    if gate > 1:
        previous = gate_row(db, user_id, region, gate - 1)
        if not previous or previous['status'] != 'completed':
            raise HTTPException(status_code=409, detail='Previous gate is incomplete')


@router.get('/gates/{region}/{gate}')
def get_gate(region: int, gate: int, db=Depends(get_supabase), user=Depends(get_current_user)):
    validate_gate(region, gate)
    user_id = int(user['user_id'])
    now = utc_now()
    row = settle_expiry(db, gate_row(db, user_id, region, gate), now)
    return public_gate(row, region, gate, now)


@router.post('/gates/{region}/{gate}/open')
def open_gate(region: int, gate: int, db=Depends(get_supabase), user=Depends(get_current_user)):
    validate_gate(region, gate)
    user_id = int(user['user_id'])
    now = utc_now()
    gate_available(db, user_id, region, gate, now)
    row = settle_expiry(db, gate_row(db, user_id, region, gate), now)
    if row and row['status'] == 'completed':
        return public_gate(row, region, gate, now)
    if row and row['status'] == 'playing':
        return public_gate(row, region, gate, now)
    if row and row['status'] == 'cooldown' and parse_time(row['cooldown_until']) > now:
        raise HTTPException(status_code=409, detail='Retry cooldown active')
    deadline = now + timedelta(minutes=GATE_MINUTES[gate - 1])
    if not row:
        # Unique PK prevents two concurrent initial attempts.
        try:
            result = db.table('adventure_puzzle_progress').insert({
                'user_id': user_id, 'region': region, 'gate': gate,
                'status': 'playing', 'started_at': now.isoformat(),
                'deadline_at': deadline.isoformat(), 'attempt_count': 1,
            }).execute()
            return public_gate(result.data[0], region, gate, now)
        except Exception as error:
            if str(getattr(error, 'code', '')) != '23505':
                raise
            row = gate_row(db, user_id, region, gate)
            return public_gate(settle_expiry(db, row, now), region, gate, now)
    result = (db.table('adventure_puzzle_progress').update({
        'status': 'playing', 'started_at': now.isoformat(),
        'deadline_at': deadline.isoformat(), 'cooldown_until': None,
        'attempt_count': int(row['attempt_count']) + 1,
    }).eq('user_id', user_id).eq('region', region).eq('gate', gate)
      .eq('status', 'cooldown').eq('cooldown_until', row['cooldown_until']).execute())
    if not result.data:
        return public_gate(settle_expiry(db, gate_row(db, user_id, region, gate), now), region, gate, now)
    return public_gate(result.data[0], region, gate, now)


@router.post('/gates/{region}/{gate}/complete')
def complete_gate(region: int, gate: int, db=Depends(get_supabase), user=Depends(get_current_user)):
    validate_gate(region, gate)
    user_id = int(user['user_id'])
    now = utc_now()
    row = settle_expiry(db, gate_row(db, user_id, region, gate), now)
    if not row or row['status'] != 'playing':
        raise HTTPException(status_code=409, detail='No active attempt')
    if parse_time(row['deadline_at']) <= now:
        settle_expiry(db, row, now)
        raise HTTPException(status_code=409, detail='Attempt expired')
    # NOTE: completion is an authenticated client report, not a server-verified solution.
    result = (db.table('adventure_puzzle_progress').update({
        'status': 'completed', 'completed_at': now.isoformat(),
    }).eq('user_id', user_id).eq('region', region).eq('gate', gate)
      .eq('status', 'playing').eq('deadline_at', row['deadline_at']).execute())
    if not result.data:
        raise HTTPException(status_code=409, detail='Attempt state changed')
    journey = current_journey(db, user_id)
    if journey and int(journey['region']) == region:
        # Completion is the departure time from the checkpoint.
        db.table('adventure_journeys').update({
            'distance': max(float(journey['distance']), gate * 3),
            'updated_at': now.isoformat(),
        }).eq('user_id', user_id).eq('updated_at', journey['updated_at']).execute()
    return public_gate(result.data[0], region, gate, now)


@router.post('/dev/reach-first-gate')
def dev_reach_first_gate(db=Depends(get_supabase), user=Depends(get_current_user)):
    import os
    if os.getenv('WEAVEMO_ADVENTURE_DEV_TEST') != '1':
        raise HTTPException(status_code=404, detail='Not found')
    user_id = int(user['user_id'])
    now = utc_now()
    journey = settle_journey(db, user_id, now)
    if not journey or int(journey['region']) != 1:
        raise HTTPException(status_code=409, detail='Start region one first')
    first = gate_row(db, user_id, 1, 1)
    if first and first['status'] == 'completed':
        raise HTTPException(status_code=409, detail='First gate already completed')
    result = (db.table('adventure_journeys').update({
        'distance': 3.0, 'updated_at': now.isoformat(),
    }).eq('user_id', user_id).eq('region', 1)
      .eq('updated_at', journey['updated_at']).execute())
    if not result.data:
        raise HTTPException(status_code=409, detail='Journey changed; retry')
    return journey_public_state(db, user_id, now)
