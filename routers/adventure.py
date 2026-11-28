# routers/adventure.py
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from fastapi import APIRouter, Depends, HTTPException
from db.database import get_supabase
from dependencies.auth import get_current_user
from services.adventure_engine import advance, utc_now, parse_time
from services.adventure_puzzle import run_puzzle

router = APIRouter()
GATE_MINUTES = (5, 8, 10, 15, 20)


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
        progress = (db.table('adventure_puzzle_progress').select('gate,status,verified_at')
                    .eq('user_id', user_id).eq('region', region).execute()).data or []
        done = {int(item['gate']) for item in progress if item['status'] == 'completed' and item['verified_at']}
        next_gate = next((gate for gate in range(1, 6) if gate not in done), None)
        # A cleared gate does not automatically authorize the next leg.
        # Existing users retain their already-reached distance via migration.
        permission = (db.table('adventure_travel_permissions').select('allowed_distance')
                      .eq('user_id', user_id).eq('region', region).limit(1).execute()).data
        allowed = float(permission[0]['allowed_distance']) if permission else 3.0
        ceiling = min(float(next_gate * 3 if next_gate else 18), allowed)
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
        if cursor > now:
            return row
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
    completed = (db.table('adventure_puzzle_progress').select('region,gate')
                 .eq('user_id', user_id).eq('status', 'completed')
                 .not_.is_('verified_at', 'null').execute()).data or []
    gate_at_checkpoint = min(5, max(1, int(distance // 3)))
    permission = (db.table('adventure_travel_permissions').select('allowed_distance')
                  .eq('user_id', user_id).eq('region', row['region']).limit(1).execute()).data
    allowed = float(permission[0]['allowed_distance']) if permission else 3.0
    departure_required = (distance < 18 and allowed <= gate_at_checkpoint * 3 and
                          (row['region'] - 1) * 5 + gate_at_checkpoint - 1 in
                          {(p['region'] - 1) * 5 + p['gate'] - 1 for p in completed})
    return {'departureRequired': departure_required, 'region': row['region'], 'distance': distance,
            'progress': round(distance / 18.0, 6), 'arrived': distance >= 18,
            'startedAt': row['started_at'],
            'completedGates': sorted((p['region'] - 1) * 5 + p['gate'] - 1 for p in completed)}

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


Language = Literal['ko', 'en']
ActionCode = Annotated[str, StringConstraints(min_length=1, max_length=32, pattern=r'^[\w-]+$')]


class PuzzleAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation: Literal['move', 'reset', 'submit']
    attempt: int = Field(ge=1, strict=True)
    revision: int = Field(ge=0, strict=True)
    move: ActionCode | None = None
    answer: str = Field(default='', max_length=80)


class RegionAdvance(BaseModel):
    region: int = Field(ge=1, le=7)


def gate_rpc(db, user_id, region, gate, operation, **parameters):
    if not (1 <= region <= 8 and 1 <= gate <= 5):
        raise HTTPException(status_code=404, detail='Unknown gate')
    return db.rpc('adventure_gate_v1', {
        'p_user_id': user_id, 'p_region': region, 'p_gate': gate,
        'p_operation': operation, **parameters,
    }).execute().data


def gate_response(result, region, gate, lang=None, board=None):
    if result['error'] == 'locked':
        raise HTTPException(status_code=409, detail='Gate is locked')
    row = result['row'] or {}
    status = 'retry_ready' if result['retryReady'] else row.get('status', 'pending')
    response = {
        'region': region, 'gate': gate, 'status': status,
        'limitSeconds': GATE_MINUTES[gate - 1] * 60,
        'deadlineAt': row.get('deadline_at') if status == 'playing' else None,
        'cooldownUntil': row.get('cooldown_until') if status == 'cooldown' else None,
        'completedAt': row.get('completed_at'),
        'attemptCount': row.get('attempt_count', 0),
        'revision': row.get('revision', 0),
        'serverNow': result['now'],
        'conflict': result['error'],
    }
    if lang and status == 'playing':
        payload = board if board is not None else run_puzzle(row, 'read', lang)
        response['puzzle'] = {**payload, 'lang': lang}
    return response


@router.get('/gates/{region}/{gate}')
def get_gate(region: int, gate: int, db=Depends(get_supabase), user=Depends(get_current_user)):
    result = gate_rpc(db, int(user['user_id']), region, gate, 'read')
    return gate_response(result, region, gate)


@router.get('/gates/{region}/{gate}/puzzle')
def get_puzzle(region: int, gate: int, lang: Language = 'ko',
               db=Depends(get_supabase), user=Depends(get_current_user)):
    result = gate_rpc(db, int(user['user_id']), region, gate, 'read')
    return gate_response(result, region, gate, lang)


@router.post('/gates/{region}/{gate}/open')
def open_gate(region: int, gate: int, lang: Language = 'ko',
              db=Depends(get_supabase), user=Depends(get_current_user)):
    user_id = int(user['user_id'])
    if not (1 <= region <= 8 and 1 <= gate <= 5):
        raise HTTPException(status_code=404, detail='Unknown gate')
    settle_journey(db, user_id)
    result = gate_rpc(db, user_id, region, gate, 'open')
    return gate_response(result, region, gate, lang)


@router.post('/gates/{region}/{gate}/puzzle')
def play_puzzle(region: int, gate: int, body: PuzzleAction, lang: Language = 'ko',
                db=Depends(get_supabase), user=Depends(get_current_user)):
    user_id = int(user['user_id'])
    current = gate_rpc(db, user_id, region, gate, 'read')
    row = current['row']
    if not row or row['status'] != 'playing':
        return gate_response(current, region, gate, lang)
    if (row['attempt_count'], row['revision']) != (body.attempt, body.revision):
        current['error'] = 'stale'
        return gate_response(current, region, gate, lang)
    board = None
    parameters = {'p_attempt': body.attempt, 'p_revision': body.revision}
    if body.operation == 'move':
        if not body.move:
            raise HTTPException(status_code=422, detail='Puzzle action is required')
        if len(row['moves']) < 256:
            board = run_puzzle(row, 'move', lang, move=body.move)
            if board.get('invalid'):
                raise HTTPException(status_code=422, detail='Invalid puzzle action')
        parameters['p_move'] = body.move
    elif body.operation == 'submit':
        parameters['p_correct'] = run_puzzle(row, 'submit', lang, answer=body.answer)['correct']
        if parameters['p_correct']:
            settle_journey(db, user_id)
    result = gate_rpc(db, user_id, region, gate, body.operation, **parameters)
    return gate_response(result, region, gate, lang, board if result['changed'] else None)



class GateDeparture(BaseModel):
    region: int = Field(ge=1, le=8)
    gate: int = Field(ge=1, le=5)


@router.post('/depart-gate')
def depart_gate(body: GateDeparture, db=Depends(get_supabase), user=Depends(get_current_user)):
    user_id = int(user['user_id'])
    # SQL verifies the gate completion and performs an atomic, monotonic unlock.
    ok = db.rpc('adventure_depart_gate_v1', {
        'p_user_id': user_id, 'p_region': body.region, 'p_gate': body.gate,
    }).execute().data
    if not ok:
        raise HTTPException(status_code=409, detail='Gate is not completed or departure is unavailable')
    return journey_public_state(db, user_id)

@router.post('/next-region')
def next_region(body: RegionAdvance, db=Depends(get_supabase), user=Depends(get_current_user)):
    # One journey ends at its own destination; never advance to another region.
    raise HTTPException(status_code=409, detail='Journey ends at its destination; next-region is disabled')
