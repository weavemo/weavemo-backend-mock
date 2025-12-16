from fastapi import APIRouter, Depends, Query
from datetime import date

from dependencies.auth import get_current_user
from db.database import supabase
from services.stats_service import (
    calculate_level,
    apply_daily_xp,
    calc_streak,
)

router = APIRouter()


@router.get("/profile")
def get_stats_profile(current_user=Depends(get_current_user)):
    user_id = current_user["id"]

    res = supabase.table("user_stats").select("*").eq("user_id", user_id).execute()
    row = res.data[0]

    return {
        "level": row["level"],
        "xp": row["xp"],
        "streak_days": row["streak_days"],
        "daily_xp": row["daily_xp"],
        "daily_xp_cap": 150,
        "plan": row["plan"],
    }


@router.post("/xp/increment")
def increment_xp(
    amount: int = Query(..., gt=0),
    source: str = Query(...),
    current_user=Depends(get_current_user),
):
    user_id = current_user["id"]
    today = date.today()

    res = supabase.table("user_stats").select("*").eq("user_id", user_id).execute()
    row = res.data[0]

    # reset daily xp if date changed
    daily_xp = row["daily_xp"]
    if row["daily_xp_date"] != today.isoformat():
        daily_xp = 0

    new_daily_xp, gained = apply_daily_xp(daily_xp, amount)
    new_xp = row["xp"] + gained
    new_level = calculate_level(new_xp)

    # streak
    delta = calc_streak(row["last_checkin_date"], today)
    new_streak = row["streak_days"]
    if delta == 1:
        new_streak += 1
    elif delta == -1:
        new_streak = 1

    supabase.table("user_stats").update({
        "xp": new_xp,
        "level": new_level,
        "daily_xp": new_daily_xp,
        "daily_xp_date": today.isoformat(),
        "streak_days": new_streak,
        "last_checkin_date": today.isoformat(),
        "updated_at": "now()",
    }).eq("user_id", user_id).execute()

    return {
        "gained_xp": gained,
        "total_xp": new_xp,
        "level": new_level,
        "streak_days": new_streak,
        "daily_xp": new_daily_xp,
    }
