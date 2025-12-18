# /routers/stats.py

from fastapi import APIRouter, Depends, Query
from datetime import date, datetime, time

from dependencies.auth import get_current_user
from db.database import get_supabase
from services.stats_service import (
    calculate_level,
    apply_daily_xp,
    calc_streak,
)

router = APIRouter()


@router.get("/profile")
def get_stats_profile(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    res = supabase.table("user_stats").select("*").eq("user_id", user_id).execute()
    if not res.data:
        supabase.table("user_stats").insert({
            "user_id": user_id,
        }).execute()
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


@router.get("/actions/completed/today")
def get_completed_actions_today(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    today = date.today()
    start = datetime.combine(today, time.min).isoformat()
    end = datetime.combine(today, time.max).isoformat()

    res = (
        supabase.table("action_logs")
        .select("action_id")
        .eq("user_id", user_id)
        .gte("started_at", start)
        .lte("started_at", end)
        .execute()
    )

    actions = [r["action_id"] for r in res.data] if res.data else []
    return {"actions": actions}


@router.post("/xp/increment")
def increment_xp(
    amount: int = Query(..., gt=0),
    source: str = Query(...),   # journal | mood | action
    action_id: int | None = Query(None),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]
    source = source.lower()
    if source == "journals":
        source = "journal"

    today = date.today()
    today_str = today.isoformat()

    # ── user_stats 조회 ────────────────────────
    res = supabase.table("user_stats").select("*").eq("user_id", user_id).execute()
    row = res.data[0]

    # ── SOURCE별 하루 1회 가드 (핵심) ──────────
    if source == "mood" and row.get("daily_mood_xp_date") == today_str:
        return {"gained_xp": 0, "blocked": True}

    if source in ["journal", "journals"] and row.get("daily_journal_xp_date") == today_str:
        return {"gained_xp": 0, "blocked": True}

    # ── DAILY XP CAP ──────────────────────────
    daily_xp = row["daily_xp"] if row["daily_xp_date"] == today_str else 0
    new_daily_xp, gained = apply_daily_xp(daily_xp, amount)

    if gained == 0:
        return {"gained_xp": 0, "blocked": True}

    new_xp = row["xp"] + gained
    new_level = calculate_level(new_xp)

    # ── STREAK ───────────────────────────────
    delta = calc_streak(row["last_checkin_date"], today)
    new_streak = row["streak_days"]
    if delta == 1:
        new_streak += 1
    elif delta == -1:
        new_streak = 1

    update_data = {
        "xp": new_xp,
        "level": new_level,
        "daily_xp": new_daily_xp,
        "daily_xp_date": today_str,
        "streak_days": new_streak,
        "last_checkin_date": today_str,
        "updated_at": "now()",
    }

    if source == "mood":
        update_data["daily_mood_xp_date"] = today_str

    if source == "journal":
        update_data["daily_journal_xp_date"] = today_str

    supabase.table("user_stats").update(update_data).eq("user_id", user_id).execute()

    return {
        "gained_xp": gained,
        "total_xp": new_xp,
        "level": new_level,
        "streak_days": new_streak,
        "daily_xp": new_daily_xp,
        "blocked": False,
    }

