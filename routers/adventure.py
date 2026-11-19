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


@router.post('/start')
def start_journey(db=Depends(get_supabase), user=Depends(get_current_user)):
    user_id = int(user['user_id'])
    existing = current_journey(db, user_id)
    if existing:
        return public_state(existing, utc_now())
    mood = latest_mood(db, user_id)
    if not mood:
        raise HTTPException(status_code=409, detail='Mood check-in required before departure')
    now = utc_now().isoformat()
    row = {'user_id': user_id, 'region': 1, 'distance': 0,
           'direction': direction_for(mood['main_valence']),
           'energy': mood['energy'], 'last_mood_id': mood['id'],
           'started_at': now, 'updated_at': now}
    db.table('adventure_journeys').upsert(row, on_conflict='user_id', ignore_duplicates=True).execute()
    stored = current_journey(db, user_id)
    if not stored:
        raise HTTPException(status_code=503, detail='Journey could not be loaded')
    return public_state(stored, utc_now())


@router.get('/state')
def get_journey_state(db=Depends(get_supabase), user=Depends(get_current_user)):
    user_id = int(user['user_id'])
    row = current_journey(db, user_id)
    if not row:
        return None
    now = utc_now()
    mood = latest_mood(db, user_id)
    if mood and mood['id'] != row['last_mood_id']:
        # Settle at each actual mood timestamp, not at the API request time.
        changes_response = (db.table('moods').select('id,energy,recorded_at')
                            .eq('user_id', user_id).gt('recorded_at', row['updated_at'])
                            .lte('recorded_at', now.isoformat())
                            .order('recorded_at').order('id').execute())
        distance = float(row['distance'])
        energy = row['energy']
        cursor = row['updated_at']
        last_id = row['last_mood_id']
        for change in changes_response.data or []:
            distance = advance(distance, energy, cursor, parse_time(change['recorded_at']))
            energy = change['energy']
            cursor = change['recorded_at']
            last_id = change['id']
        distance = advance(distance, energy, cursor, now)
        if last_id != row['last_mood_id']:
            updated = (db.table('adventure_journeys')
                       .update({'distance': distance, 'energy': energy,
                                'last_mood_id': last_id, 'updated_at': now.isoformat()})
                       .eq('user_id', user_id).eq('last_mood_id', row['last_mood_id'])
                       .execute())
            row = updated.data[0] if updated.data else current_journey(db, user_id)
    return public_state(row, now)


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
    journey = current_journey(db, user_id)
    if not journey or int(journey['region']) != region:
        raise HTTPException(status_code=409, detail='Journey is not in this region')
    distance = advance(journey['distance'], journey['energy'], journey['updated_at'], now)
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
    return public_gate(result.data[0], region, gate, now)
