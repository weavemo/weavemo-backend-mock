# weavemo-backend-mock/routers/journal.py

import logging
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Header, Body

from dependencies.auth import get_current_user
from db.database import get_supabase
from schemas.journal import JournalCreate
from services.mood_analysis_service import build_reflection_analysis

router = APIRouter()
logger = logging.getLogger(__name__)


def grant_journal_xp(
    supabase,
    user_id: int,
    tz_offset_min: int,
):
    result = supabase.rpc(
        "grant_activity_xp",
        {
            "p_user_id": user_id,
            "p_source": "journal",
            "p_action_id": None,
            "p_tz_offset_min": tz_offset_min,
        },
    ).execute()

    return result.data


@router.post("")
def create_journal(
    body: JournalCreate,
    current_user=Depends(get_current_user),
    tz_offset_min: int = Header(
        0,
        convert_underscores=False,
        ge=-840,
        le=840,
    ),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    today = date.today()
    today_str = today.isoformat()
    start = datetime.combine(today, time.min).isoformat()
    end = datetime.combine(today, time.max).isoformat()

    # 기존 하루 1회 제한 유지
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

    supabase.table("journals").insert({
        "user_id": user_id,
        "content": body.content,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    # total_journals는 기존에 설치한 DB 트리거가 갱신한다.
    # XP와 연속 활동 집계는 공용 DB 함수가 처리한다.
    xp_result = {}
    xp_pending = False

    try:
        xp_result = grant_journal_xp(
            supabase,
            user_id,
            tz_offset_min,
        )
    except Exception:
        xp_pending = True
        logger.exception(
            "Journal saved but XP grant failed: user_id=%s",
            user_id,
        )

    response = {
        "ok": True,
        "blocked": False,
        "xp_gained": xp_result.get("gained_xp", 0),
        "xp_pending": xp_pending,
    }

    if "level" in xp_result:
        response["level"] = xp_result["level"]

    if "streak_days" in xp_result:
        response["streak_days"] = xp_result["streak_days"]

    return response


# ==============================
# Daily Reflection
# ==============================

@router.post("/daily")
def create_daily_reflection(
    content: str = Body(..., embed=True),
    current_user=Depends(get_current_user),
    tz_offset_min: int = Header(
        0,
        convert_underscores=False,
        ge=-840,
        le=840,
    ),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    today = date.today()
    today_str = today.isoformat()
    start = datetime.combine(today, time.min).isoformat()
    end = datetime.combine(today, time.max).isoformat()
    now = datetime.utcnow().isoformat()

    # 기존 오늘 journal 조회 유지
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

    # 기존 회고 분석 처리 유지
    metrics_res = supabase.rpc(
        "get_today_mood_metrics",
        {"uid": user_id},
    ).execute()

    if metrics_res.data:
        metrics = (
            metrics_res.data[0]
            if isinstance(metrics_res.data, list)
            else metrics_res.data
        )

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

    # 기존처럼 처음 생성한 경우에만 XP 요청
    gained = 0
    xp_pending = False

    if created:
        try:
            xp_result = grant_journal_xp(
                supabase,
                user_id,
                tz_offset_min,
            )

            gained = xp_result.get("gained_xp", 0)
        except Exception:
            xp_pending = True
            logger.exception(
                "Reflection saved but XP grant failed: journal_id=%s",
                journal_id,
            )

    return {
        "ok": True,
        "journal_id": journal_id,
        "xp_gained": gained,
        "xp_pending": xp_pending,
    }


# ==============================
# Daily Reflection Review
# ==============================

@router.get("/daily")
def get_daily_reflection(
    date_value: date,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    start = datetime.combine(date_value, time.min).isoformat()
    end = datetime.combine(date_value, time.max).isoformat()

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
