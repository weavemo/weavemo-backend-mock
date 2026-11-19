# routers/adventure.py
from fastapi import APIRouter, Depends, HTTPException
from db.database import get_supabase
from dependencies.auth import get_current_user
from services.adventure_engine import advance, public_state, utc_now

router = APIRouter()


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
    # Internal direction mapping; never expose the emotional cause.
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
    row = {
        'user_id': user_id, 'region': 1, 'distance': 0,
        'direction': direction_for(mood['main_valence']),
        'energy': mood['energy'], 'last_mood_id': mood['id'],
        'started_at': now, 'updated_at': now,
    }
    # Unique user_id prevents duplicate journeys from concurrent starts.
    result = db.table('adventure_journeys').upsert(row, on_conflict='user_id', ignore_duplicates=True).execute()
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
        # Settle travel at the old energy, then switch energy for future time.
        distance = advance(row['distance'], row['energy'], row['updated_at'], now)
        changes = {'distance': distance, 'energy': mood['energy'],
                   'last_mood_id': mood['id'], 'updated_at': now.isoformat()}
        updated = (db.table('adventure_journeys').update(changes)
                   .eq('user_id', user_id).eq('last_mood_id', row['last_mood_id'])
                   .execute())
        if updated.data:
            row = updated.data[0]
        else:
            row = current_journey(db, user_id)
    return public_state(row, now)
