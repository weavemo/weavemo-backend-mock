# /routers/stats.py

from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import date, datetime, time, timezone, timedelta
import traceback

from dependencies.auth import get_current_user
from db.database import get_supabase

router = APIRouter()

def _get_or_create_user_stats(supabase, user_id: int):
    try:
        res = supabase.table("user_stats").select("*").eq("user_id", user_id).execute()
    except Exception:
        # 🔥 fallback (절대 터지지 않게)
        return {
            "user_id": user_id,
            "xp": 0,
            "level": 1,
            "daily_xp": 0,
            "daily_xp_date": None,
            "streak_days": 0,
            "plan": "free",
        }
    if not res.data:
        supabase.table("user_stats").insert({
            "user_id": user_id,
            "xp": 0,
            "level": 1,
            "daily_xp": 0,
            "daily_xp_date": None,
            "streak_days": 0,
            "plan": "free",
        }).execute()
        res = supabase.table("user_stats").select("*").eq("user_id", user_id).execute()
    return (res.data or [])[0]

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
def get_stats_profile(
    tz_offset_min: int = Query(0),
    current_user=Depends(get_current_user),
):    
    try:
        supabase = get_supabase()
        user_id = current_user["user_id"]
    
        try:
            row = _get_or_create_user_stats(supabase, user_id)
        except Exception:
            row = {
                "xp": 0,
                "level": 1,
                "streak_days": 0,
                "daily_xp": 0,
                "daily_xp_date": None,
                "plan": "free",
            }
        today_str, _, _ = _user_today_range_utc(tz_offset_min)
    
        daily_xp = row["daily_xp"] if row["daily_xp_date"] == today_str else 0
    
        return {
            "level": row["level"],
            "xp": row["xp"],
            "streak_days": row["streak_days"],
            "daily_xp": daily_xp,
            "daily_xp_cap": 150,
            "plan": row.get("plan", "free"),
        }
    except Exception:
        traceback.print_exc()
        raise


@router.get("/actions/completed/today")
def get_completed_actions_today(tz_offset_min: int = Query(0), current_user=Depends(get_current_user),):
    supabase = get_supabase()
    user_id = current_user.get("user_id") or current_user.get("id")

    _, start, end = _user_today_range_utc(tz_offset_min)

    try:
        res = (
            supabase.table("action_logs")
            .select("action_id")
            .eq("user_id", user_id)
            .gte("completed_at", start)
            .lte("completed_at", end)
            .execute()
        )
    except Exception:
        return {"actions":[]}

    actions = [r["action_id"] for r in res.data] if res.data else []
    return {"actions": actions}


@router.post("/xp/increment")
def increment_xp(
    amount: int = Query(None, gt=0),
    source: str = Query(None),
    action_id: int | None = Query(None),
    tz_offset_min: int = Query(0, ge=-840, le=840),
    current_user=Depends(get_current_user),
):
    if amount is None or source is None:
        raise HTTPException(
            status_code=400,
            detail="amount and source are required",
        )

    source = source.strip().lower()

    if source == "journals":
        source = "journal"

    expected_amounts = {
        "mood": 10,
        "journal": 10,
        "action": 15,
    }

    if source not in expected_amounts:
        raise HTTPException(
            status_code=400,
            detail="Invalid XP source",
        )

    if amount != expected_amounts[source]:
        raise HTTPException(
            status_code=400,
            detail="Invalid XP amount",
        )

    if source == "action" and (
        action_id is None or action_id <= 0
    ):
        raise HTTPException(
            status_code=400,
            detail="action_id is required",
        )

    supabase = get_supabase()

    result = supabase.rpc(
        "grant_activity_xp",
        {
            "p_user_id": current_user["user_id"],
            "p_source": source,
            "p_action_id": action_id,
            "p_tz_offset_min": tz_offset_min,
        },
    ).execute()

    return result.dataf

@router.post("/actions/feedback")
def save_action_feedback(
    action_id: int = Query(None),
    feedback: int = Query(None),  # -1 | 0 | 1
    current_user=Depends(get_current_user),
):
    if action_id is None or feedback is None:
        raise ValueError("action_id and feedback are required")
    
    supabase = get_supabase()
    user_id = current_user["user_id"]

    supabase.table("action_logs").update({
        "feedback": feedback,
    }).eq("user_id", user_id).eq("action_id", action_id).is_("feedback", None).execute()

    return {"ok": True}
