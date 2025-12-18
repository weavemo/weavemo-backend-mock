from fastapi import APIRouter, Depends
from datetime import date, datetime, time

from dependencies.auth import get_current_user
from db.database import get_supabase
from schemas.journal import JournalCreate
from services.stats_service import (
    apply_daily_xp,
    calculate_level,
    calc_streak,
)

router = APIRouter()


@router.post("")
def create_journal(
    body: JournalCreate,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    today = date.today()
    today_str = today.isoformat()
    start = datetime.combine(today, time.min).isoformat()
    end = datetime.combine(today, time.max).isoformat()

    # 🔒 하루 1회 제한
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
        return {
            "ok": False,
            "blocked": True,
            "xp_gained": 0,
        }

    # 1️⃣ journal 저장
    supabase.table("journals").insert({
        "user_id": user_id,
        "content": body.content,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    # 2️⃣ user_stats 조회
    stats_res = (
        supabase.table("user_stats")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    row = stats_res.data[0]

    # 3️⃣ total_journals +1
    supabase.table("user_stats").update({
        "total_journals": row["total_journals"] + 1
    }).eq("user_id", user_id).execute()

    # 4️⃣ XP (+10, daily cap 적용)
    daily_xp = row["daily_xp"]
    if row["daily_xp_date"] != today_str:
        daily_xp = 0

    new_daily_xp, gained = apply_daily_xp(daily_xp, 10)
    new_xp = row["xp"] + gained if gained > 0 else row["xp"]
    new_level = calculate_level(new_xp)

    # 5️⃣ streak 계산
    delta = calc_streak(row["last_checkin_date"], today)
    new_streak = row["streak_days"]
    if delta == 1:
        new_streak += 1
    elif delta == -1:
        new_streak = 1

    # 6️⃣ stats 업데이트
    supabase.table("user_stats").update({
        "xp": new_xp,
        "level": new_level,
        "daily_xp": new_daily_xp,
        "daily_xp_date": today_str,
        "streak_days": new_streak,
        "last_checkin_date": today_str,
        "updated_at": "now()",
    }).eq("user_id", user_id).execute()

    return {
        "ok": True,
        "blocked": False,
        "xp_gained": gained,
        "level": new_level,
        "streak_days": new_streak,
    }
