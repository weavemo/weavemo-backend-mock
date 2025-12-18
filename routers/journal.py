# routers/journal.py
from fastapi import APIRouter, Depends
from datetime import date, datetime, time
from dependencies.auth import get_current_user
from db.database import get_supabase
from schemas.journal import JournalCreate
from services.stats_service import apply_daily_xp, calculate_level, calc_streak

router = APIRouter()

@router.post("")
def create_journal(
    body: JournalCreate,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]
    today = date.today()
    start = datetime.combine(today, time.min).isoformat()
    end = datetime.combine(today, time.max).isoformat()

    # 🔒 하루 1회 체크
    exists = (
        supabase.table("journals")
        .select("id")
        .eq("user_id", user_id)
        .gte("created_at", start)
        .lte("created_at", end)
        .limit(1)
        .execute()
    )

    if exists.data:
        return {"ok": False, "xp_gained": 0, "blocked": True}

    # 1) journal 저장
    supabase.table("journals").insert({
        "user_id": user_id,
        "content": body.content,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()
    return {
        "ok": True,
        "blocked": False,
    }

    # 2) stats 업데이트 (+10 XP)
    stats_res = (
        supabase.table("user_stats")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    row = stats_res.data[0]

    new_daily_xp, gained = apply_daily_xp(row["daily_xp"], 10)
    new_xp = row["xp"] + gained
    new_level = calculate_level(new_xp)

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
        "daily_xp_date": today,
        "streak_days": new_streak,
        "last_checkin_date": today,
    }).eq("user_id", user_id).execute()

    return {
        "ok": True,
        "xp_gained": gained,
        "level": new_level,
        "streak_days": new_streak,
        "blocked": False,
    }
