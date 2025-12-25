# routers/journal_entries.py
from fastapi import APIRouter, Depends, Query, Body
from datetime import date, datetime
from datetime import date as date_type
from dependencies.auth import get_current_user
from db.database import get_supabase
from services.stats_service import apply_daily_xp, calculate_level, calc_streak

router = APIRouter()

@router.post("")
def create_journal_entry(
    content: str = Body(...),
    date: date = Body(...),
    type: str = Body(...),
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
    today_str = datetime.utcnow().date().isoformat()
    stats = supabase.table("user_stats").select("*").eq("user_id", user_id).execute().data[0]

    # 🔒 journal / journal_entries 통합 하루 1회 XP 가드
    if stats["daily_journal_xp_date"] == today_str:
         gained = 0
         new_xp = stats["xp"]
         new_level = stats["level"]
         new_daily_xp = stats["daily_xp"]
    else:
         new_daily_xp, gained = apply_daily_xp(0, 10)
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

@router.get("/dates")
def get_entry_dates(
    month: str = Query(..., regex=r"^\d{4}-\d{2}$"),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    start = f"{month}-01"
    year, mon = map(int, month.split("-"))
    if mon == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{mon + 1:02d}-01"

    res = (
        supabase.table("journal_entries")
        .select("date")
        .eq("user_id", user_id)
        .gte("date", start)
        .lt("date", end)
        .execute()
    )

    dates = sorted({row["date"] for row in res.data})
    return {"dates": dates}
    return {"items": res.data}
