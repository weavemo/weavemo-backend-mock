from fastapi import APIRouter, Depends, Query, Body, Header, HTTPException
from datetime import date, datetime
from math import isfinite
from dependencies.auth import get_current_user
from db.database import get_supabase
from uuid import UUID
from services.journal_entry_save import insert_journal_entry

router = APIRouter()


def validate_owned_card_background(supabase, auth_uid: str, background_key: str | None) -> str | None:
    if background_key is None:
        return None
    key = background_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="Invalid background key")
    reward_res = (
        supabase.table("reward_items").select("id, reward_types(key)")
        .eq("key", key).limit(1).execute()
    )
    reward = reward_res.data[0] if reward_res.data else None
    reward_type = reward.get("reward_types") if reward else None
    if not isinstance(reward_type, dict) or reward_type.get("key") != "card_background":
        raise HTTPException(status_code=400, detail="Invalid card background reward")
    inventory_res = (
        supabase.table("user_reward_inventory").select("reward_item_id")
        .eq("user_id", auth_uid).eq("reward_item_id", reward["id"]).limit(1).execute()
    )
    if not inventory_res.data:
        raise HTTPException(status_code=403, detail="Card background not owned")
    return key


@router.post("")
def create_journal_entry(
    content: str = Body(None),
    date: date = Body(None),
    type: str = Body(None),
    background_reward_key: str | None = Body(None),
    mood_valence: float | None = Body(None, ge=-2, le=2, allow_inf_nan=False),
    mood_energy: float | None = Body(None, ge=1, le=5, allow_inf_nan=False),
    client_request_id: UUID | None = Body(None),
    tz_offset_min: int = Header(0),
    current_user=Depends(get_current_user),
):
    if content is None or date is None or type is None:
        raise HTTPException(status_code=400, detail="content, date, type required")
    if type == "gratitude" and not 10 <= len(content.strip()) <= 300:
        raise HTTPException(status_code=400, detail="Gratitude content must be 10 to 300 characters")
    supabase = get_supabase()
    user_id = current_user["user_id"]
    background_key = validate_owned_card_background(
        supabase, current_user["auth_uid"], background_reward_key
    )
    payload = {
        "user_id": user_id, "content": content, "date": date.isoformat(), "type": type,
        "created_at": datetime.utcnow().isoformat(),
        "background_reward_key": background_key,
        "mood_valence": mood_valence, "mood_energy": mood_energy,
    }
    if client_request_id is not None:
        payload["client_request_id"] = str(client_request_id)
    return insert_journal_entry(supabase, payload)


@router.post("/reflection")
def create_reflection(
    content: str = Body(None),
    week_start: date = Body(None),
    background_reward_key: str | None = Body(None),
    mood_valence: float | None = Body(None, ge=-2, le=2, allow_inf_nan=False),
    mood_energy: float | None = Body(None, ge=1, le=5, allow_inf_nan=False),
    current_user=Depends(get_current_user),
):
    if content is None or week_start is None:
        raise HTTPException(status_code=400, detail="content, week_start required")
    supabase = get_supabase()
    user_id = current_user["user_id"]
    exists = (
        supabase.table("journal_entries").select("id").eq("user_id", user_id)
        .eq("type", "reflection").eq("date", week_start.isoformat()).limit(1).execute()
    )
    if exists.data:
        return {"ok": False, "error": "reflection_already_exists"}
    background_key = validate_owned_card_background(supabase, current_user["auth_uid"], background_reward_key)
    supabase.table("journal_entries").insert({
        "user_id": user_id, "content": content, "date": week_start.isoformat(),
        "type": "reflection", "created_at": datetime.utcnow().isoformat(),
        "background_reward_key": background_key, "mood_valence": mood_valence, "mood_energy": mood_energy,
    }).execute()
    return {"ok": True}


@router.get("/reflection")
def get_reflection(week_start: date = Query(None), current_user=Depends(get_current_user)):
    if week_start is None:
        raise ValueError("week_start required")
    supabase = get_supabase()
    user_id = current_user["user_id"]
    res = (
        supabase.table("journal_entries")
        .select("content, date, created_at, background_reward_key, mood_valence, mood_energy")
        .eq("user_id", user_id).eq("type", "reflection")
        .eq("date", week_start.isoformat()).limit(1).execute()
    )
    if not res.data:
        return {"item": None}
    return {"item": res.data[0]}


@router.get("/reflection-mood")
def get_reflection_mood(week_start: date = Query(...), current_user=Depends(get_current_user)):
    """Use the existing moods.date values for the selected seven-day week."""
    supabase = get_supabase()
    week_end = date.fromordinal(week_start.toordinal() + 7)
    offset = 0
    valences = []
    energies = []
    count = 0
    while True:
        response = (
            supabase.table("moods").select("id, main_valence, energy")
            .eq("user_id", current_user["user_id"])
            .gte("date", week_start.isoformat()).lt("date", week_end.isoformat())
            .order("id").range(offset, offset + 499).execute()
        )
        rows = response.data or []
        count += len(rows)
        for row in rows:
            valence = row.get("main_valence")
            energy = row.get("energy")
            if isinstance(valence, (int, float)) and isfinite(valence) and -2 <= valence <= 2:
                valences.append(valence)
            if isinstance(energy, (int, float)) and isfinite(energy) and 1 <= energy <= 5:
                energies.append(energy)
        if len(rows) < 500:
            break
        offset += len(rows)
    return {
        "count": count,
        "valence": sum(valences) / len(valences) if valences else None,
        "energy": sum(energies) / len(energies) if energies else None,
    }


@router.get("/reflection_weeks")
def get_reflection_weeks(month: str = Query(None), current_user=Depends(get_current_user)):
    if month is None:
        raise ValueError("month required")
    supabase = get_supabase()
    user_id = current_user["user_id"]
    year, mon = map(int, month.split("-"))
    start = date(year, mon, 1)
    if mon == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, mon + 1, 1)
    res = (
        supabase.table("journal_entries").select("date").eq("user_id", user_id)
        .eq("type", "reflection").gte("date", start.isoformat()).lt("date", end.isoformat()).execute()
    )
    weeks = sorted({row["date"] for row in res.data})
    return {"weeks": weeks}


@router.get("/by-date")
def get_by_date(date: date = Query(None), current_user=Depends(get_current_user)):
    if date is None:
        raise ValueError("date required")
    supabase = get_supabase()
    user_id = current_user["user_id"]
    res = (
        supabase.table("journal_entries").select("*").eq("user_id", user_id)
        .eq("date", date.isoformat()).order("created_at", desc=False).execute()
    )
    return {"items": res.data}


@router.get("/dates")
def get_entry_dates(month: str = Query(None), current_user=Depends(get_current_user)):
    if month is None:
        raise ValueError("month required")
    supabase = get_supabase()
    user_id = current_user["user_id"]
    start = f"{month}-01"
    year, mon = map(int, month.split("-"))
    if mon == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{mon + 1:02d}-01"
    res = (
        supabase.table("journal_entries").select("date").eq("user_id", user_id)
        .gte("date", start).lt("date", end).execute()
    )
    dates = sorted({row["date"] for row in res.data})
    return {"dates": dates}


@router.get("/count")
def get_journal_count(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]
    stats_res = (
        supabase.table("user_stats").select("total_journals")
        .eq("user_id", user_id).limit(1).execute()
    )
    if not stats_res.data:
        return {"count": 0}
    return {"count": stats_res.data[0].get("total_journals", 0)}


@router.get("/reflections")
def list_weekly_reflections(
    offset: int = Query(0, ge=0), limit: int = Query(12, ge=1, le=50),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]
    result = (
        supabase.table("journal_entries")
        .select("id, date, content, created_at, background_reward_key, mood_valence, mood_energy")
        .eq("user_id", user_id).eq("type", "reflection")
        .order("date", desc=True).order("id", desc=True).range(offset, offset + limit).execute()
    )
    rows = result.data or []
    return {"items": rows[:limit], "has_more": len(rows) > limit}
