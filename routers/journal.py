#weavemo-backend-mock/routers/journal.py

from fastapi import APIRouter, Depends
from datetime import date, datetime, time

from dependencies.auth import get_current_user
from db.database import get_supabase
from schemas.journal import JournalCreate
from services.mood_analysis_service import build_reflection_analysis
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

# ==============================
# Daily Reflection (일간 회고)
# ==============================

@router.post("/daily")
def create_daily_reflection(
    content: str,
    current_user=Depends(get_current_user),
):
    """
    일간 회고 전용 엔드포인트
    - 하루 1개 (있으면 update)
    - metrics 기반 요약 생성
    - journal_analysis에 저장
    - XP / streak 로직은 기존 create_journal과 동일
    """

    supabase = get_supabase()
    user_id = current_user["user_id"]

    today = date.today()
    today_str = today.isoformat()
    start = datetime.combine(today, time.min).isoformat()
    end = datetime.combine(today, time.max).isoformat()
    now = datetime.utcnow().isoformat()

    # 1️⃣ 오늘 journal 조회
    exists = (
        supabase.table("journals")
        .select("id")
        .eq("user_id", user_id)
        .gte("created_at", start)
        .lte("created_at", end)
        .limit(1)
        .execute()
    )

    created = False

    if exists.data:
        journal_id = exists.data[0]["id"]
        supabase.table("journals").update({
            "content": content,
            "updated_at": now,
        }).eq("id", journal_id).execute()
    else:
        res = supabase.table("journals").insert({
            "user_id": user_id,
            "content": content,
            "created_at": now,
            "updated_at": now,
        }).execute()
        journal_id = res.data[0]["id"]
        created = True

    # 2️⃣ metrics → 요약 생성 → journal_analysis 저장
    metrics_res = supabase.rpc(
        "get_today_mood_metrics",
        {"uid": user_id}
    ).execute()

    if metrics_res.data:
        metrics = metrics_res.data[0] if isinstance(metrics_res.data, list) else metrics_res.data
        analysis = build_reflection_analysis(metrics)

        existing_analysis = (
            supabase.table("journal_analysis")
            .select("id")
            .eq("journal_id", journal_id)
            .execute()
        )

        if existing_analysis.data:
            supabase.table("journal_analysis").update({
                "summary_text": "\n".join(analysis["summary"]),
                "updated_at": now,
            }).eq("journal_id", journal_id).execute()
        else:
            supabase.table("journal_analysis").insert({
                "journal_id": journal_id,
                "summary_text": "\n".join(analysis["summary"]),
                "created_at": now,
            }).execute()

    # 3️⃣ XP / streak 은 '처음 생성'일 때만 (공용 로직 재사용)
    if created:
        stats_res = (
            supabase.table("user_stats")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        row = stats_res.data[0]

        supabase.table("user_stats").update({
            "total_journals": row["total_journals"] + 1
        }).eq("user_id", user_id).execute()

        daily_xp = row["daily_xp"]
        if row["daily_xp_date"] != today_str:
            daily_xp = 0

        new_daily_xp, gained = apply_daily_xp(daily_xp, 10)
        new_xp = row["xp"] + gained if gained > 0 else row["xp"]
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
            "daily_xp_date": today_str,
            "streak_days": new_streak,
            "last_checkin_date": today_str,
            "updated_at": now,
        }).eq("user_id", user_id).execute()
    else:
        gained = 0

    return {
        "ok": True,
        "journal_id": journal_id,
        "xp_gained": gained,
    }

# ==============================
# Daily Reflection Review (조회)
# ==============================

@router.get("/daily")
def get_daily_reflection(
    date_value: date,
    current_user=Depends(get_current_user),
):
    """
    일간 회고 조회
    - journals + journal_analysis
    - 읽기 전용
    """

    supabase = get_supabase()
    user_id = current_user["user_id"]

    start = datetime.combine(date_value, time.min).isoformat()
    end = datetime.combine(date_value, time.max).isoformat()

    # 1️⃣ journal 조회
    journal_res = (
        supabase.table("journals")
        .select("id, content, created_at")
        .eq("user_id", user_id)
        .gte("created_at", start)
        .lte("created_at", end)
        .limit(1)
        .execute()
    )

    if not journal_res.data:
        return {
            "exists": False,
        }

    journal = journal_res.data[0]

    # 2️⃣ journal_analysis 조회
    analysis_res = (
        supabase.table("journal_analysis")
        .select("summary_text")
        .eq("journal_id", journal["id"])
        .limit(1)
        .execute()
    )

    summary = None
    if analysis_res.data:
        summary = analysis_res.data[0]["summary_text"]

    return {
        "exists": True,
        "journal_id": journal["id"],
        "content": journal["content"],
        "summary_text": summary,
        "created_at": journal["created_at"],
    }
