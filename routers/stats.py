# /routers/stats.py

from fastapi import APIRouter, Depends, Query
from datetime import date, datetime, time, timezone, timedelta

from dependencies.auth import get_current_user
from db.database import get_supabase
from services.stats_service import (
    calculate_level,
    apply_daily_xp,
    calc_streak,
)

router = APIRouter()

def _user_today_range_utc(tz_offset_min: int):
    """
    tz_offset_min: user timezone offset in minutes (KST = 540)
    returns: (today_str, utc_start_iso, utc_end_iso)
    """
    offset = timedelta(minutes=tz_offset_min)
    now_utc = datetime.now(timezone.utc)
    user_now = now_utc + offset
    user_today = user_now.date()

    user_start = datetime.combine(user_today, time.min)
    user_end = datetime.combine(user_today, time.max)

    utc_start = (user_start - offset)
    utc_end = (user_end - offset)

    return (
        user_today.isoformat(),
        utc_start.isoformat(),
        utc_end.isoformat(),
    )

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
def get_completed_actions_today(tz_offset_min: int = Query(0), current_user=Depends(get_current_user),):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    _, start, end = _user_today_range_utc(tz_offset_min)

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
    tz_offset_min: int = Query(0),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]
    source = source.lower()
    if source == "journals":
        source = "journal"

    today_str, start, end = _user_today_range_utc(tz_offset_min)

    # ── user_stats 조회 ────────────────────────
    res = supabase.table("user_stats").select("*").eq("user_id", user_id).execute()
    row = res.data[0]

    # ── ACTION 하루 1회 가드 (추가된 유일한 로직) ──────────
    if source == "action":
        if action_id is None:
            return {"gained_xp": 0, "blocked": True}

        # start / end already calculated in user timezone (UTC)
        existing = (
            supabase.table("action_logs")
            .select("id")
            .eq("user_id", user_id)
            .eq("action_id", action_id)
#            .gte("started_at", start)
#            .lte("started_at", end)
            .gte("completed_at", start)
            .lte("completed_at", end)
            .limit(1)
            .execute()
        )

        if existing.data:
            return {"gained_xp": 0, "blocked": True}

    # ── SOURCE별 하루 1회 가드 (기존 그대로) ──────────
    if source == "mood" and row.get("daily_mood_xp_date") == today_str:
        return {"gained_xp": 0, "blocked": True}

    if source in ["journal", "journals"] and row.get("daily_journal_xp_date") == today_str:
        return {"gained_xp": 0, "blocked": True}

    # ── DAILY XP CAP (기존 그대로) ─────────────────
    daily_xp = row["daily_xp"] if row["daily_xp_date"] == today_str else 0
    new_daily_xp, gained = apply_daily_xp(daily_xp, amount)

    if gained == 0:
        return {"gained_xp": 0, "blocked": True}

    new_xp = row["xp"] + gained
    new_level = calculate_level(new_xp)

    # ── STREAK (기존 그대로) ─────────────────────
    delta = calc_streak(row["last_checkin_date"], date.fromisoformat(today_str))
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

    # ── ACTION 완료 기록 (추가된 유일한 insert) ──────────
#    if source == "action":
#        supabase.table("action_logs").insert({
#            "user_id": user_id,
#            "action_id": action_id,
#            "started_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
#        }).execute()
    if source == "action":
       supabase.table("action_logs").insert({
           "user_id": user_id,
           "action_id": action_id,
           # started_at은 DB default(now())
           "completed_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
       }).execute()

    return {
        "gained_xp": gained,
        "total_xp": new_xp,
        "level": new_level,
        "streak_days": new_streak,
        "daily_xp": new_daily_xp,
        "blocked": False,
    }
