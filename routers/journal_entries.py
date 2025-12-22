# routers/journal_entries.py
from fastapi import APIRouter, Depends, Query
from datetime import date, datetime
from dependencies.auth import get_current_user
from db.database import get_supabase
from services.stats_service import apply_daily_xp, calculate_level, calc_streak

router = APIRouter(prefix="/journal-entries")

@router.post("")
def create_journal_entry(
    content: str,
    date: date,
    type: str,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    # insert entry
    supabase.table("journal_entries").insert({
        "user_id": user_id,
        "content": content,
        "date": date.isoformat(),
        "type": type,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    # XP 처리 (기존 stats 로직 재사용)
    today_str = date.isoformat()
    stats = supabase.table("user_stats").select("*").eq("user_id", user_id).execute().data[0]

    daily_xp = stats["daily_xp"] if stats["daily_journal_xp_date"] == today_str else 0
    new_daily_xp, gained = apply_daily_xp(daily_xp, 10)
    new_xp = stats["xp"] + gained if gained > 0 else stats["xp"]
    new_level = calculate_level(new_xp)

    supabase.table("user_stats").update({
        "xp": new_xp,
        "level": new_level,
        "daily_xp": new_daily_xp,
        "daily_journal_xp_date": today_str,
        "updated_at": "now()",
    }).eq("user_id", user_id).execute()

    return {"ok": True, "xp_gained": gained, "level": new_level}


@router.get("/by-date")
def get_by_date(
    date: date = Query(...),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    res = (
        supabase.table("journal_entries")
        .select("*")
        .eq("user_id", user_id)
        .eq("date", date.isoformat())
        .order("created_at", desc=False)
        .execute()
    )

    return {"items": res.data}
