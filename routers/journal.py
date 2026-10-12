# weavemo-backend-mock/routers/journal.py

import logging
from datetime import date, datetime, time
from services.mood_service import get_mood_analysis
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

    # total_journals는 DB 트리거에서 처리
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
    start = datetime.combine(today, time.min).isoformat()
    end = datetime.combine(today, time.max).isoformat()
    now = datetime.utcnow().isoformat()

    # 기존 날짜 조회 방식 유지
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
        journal_id = exists.data[0]["id"]

        supabase.table("journals").update({
            "content": content,
            "updated_at": now,
        }).eq("id", journal_id).execute()
    else:
        result = supabase.table("journals").insert({
            "user_id": user_id,
            "content": content,
            "created_at": now,
            "updated_at": now,
        }).execute()

        journal_id = result.data[0]["id"]

    # 저장 성공 이후 XP 처리
    # 수정·재요청 시에도 공용 함수가 하루 중복 지급을 막는다.
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
            "Reflection saved but XP grant failed: journal_id=%s",
            journal_id,
        )

       analysis_pending = False

    try:
        mood_analysis = get_mood_analysis(
            supabase=supabase,
            user_id=user_id,
            range_key="today",
            tz_offset_min=tz_offset_min,
        )

        if mood_analysis.points:
            analysis = build_reflection_analysis(
                mood_analysis
            )

            existing_analysis = (
                supabase.table("journal_analysis")
                .select("id")
                .eq("journal_id", journal_id)
                .limit(1)
                .execute()
            )

            summary_text = "\n".join(analysis["summary"])

            if existing_analysis.data:
                supabase.table("journal_analysis").update({
                    "summary_text": summary_text,
                    "updated_at": now,
                }).eq(
                    "id",
                    existing_analysis.data[0]["id"],
                ).execute()
            else:
                supabase.table("journal_analysis").insert({
                    "journal_id": journal_id,
                    "summary_text": summary_text,
                    "created_at": now,
                }).execute()
        else:
            # 감정 기록이 없으면 분석 문장을 만들지 않는다.
            analysis_pending = True

    except Exception:
        analysis_pending = True
        logger.exception(
            "Reflection saved but analysis failed: journal_id=%s",
            journal_id,
        )
        

    return {
        "ok": True,
        "journal_id": journal_id,
        "xp_gained": xp_result.get("gained_xp", 0),
        "xp_pending": xp_pending,
        "analysis_pending": analysis_pending,
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
