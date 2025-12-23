# weavemo-backend/routers/mood.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from db.database import get_supabase
from dependencies.auth import get_current_user
from schemas.mood import MoodInput, MoodResult, MoodAnalysisResponse
from services.mood_service import get_mood_analysis

router = APIRouter()


@router.post(
    "/submit",
    response_model=MoodResult,
    status_code=status.HTTP_200_OK,
)
def submit_mood(
    payload: MoodInput,
    supabase=Depends(get_supabase),
    current_user=Depends(get_current_user),
):
    """
    Week 3 (LOCK):
    - 하루 1회 (user_id + UTC date) upsert
    - tags: 전체 삭제 후 재삽입
    """

    # 0️⃣ 내부 user_id (BIGINT)
    user_id: int = current_user["user_id"]

    # 1️⃣ UTC 기준 날짜
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date().isoformat()

    # 2️⃣ 오늘 mood 조회/항상 insert(하루 여러번 기록 허용)
    mood_write: Dict[str, Any] = {
        "user_id": user_id,
        "date": today,
        "recorded_at": now_utc.isoformat(),
        "main_valence": payload.mainValence,
        "energy": payload.energy,
        "trigger_type": payload.triggerType,
        "note": payload.note,
    }

    created = supabase.table("moods").insert(mood_write).execute()
    mood_id = created.data[0]["id"]


    # 4️⃣ 태그 동기화
    tag_codes: List[str] = payload.tagIds or []

    supabase.table("mood_emotion_tags").delete().eq("mood_id", mood_id).execute()

    if tag_codes:
        tag_rows = (
            supabase.table("emotion_tags")
            .select("id, code")
            .in_("code", tag_codes)
            .execute()
            .data
            or []
        )

        found = {t["code"] for t in tag_rows}
        missing = [c for c in tag_codes if c not in found]
        if missing:
            raise HTTPException(
                status_code=400,
                detail={"message": "Unknown tag codes", "missing": missing},
            )

        joins = [{"mood_id": mood_id, "tag_id": t["id"]} for t in tag_rows]
        supabase.table("mood_emotion_tags").insert(joins).execute()

    return MoodResult(
        moodId=mood_id,
        date=today,
        mainValence=payload.mainValence,
        energy=payload.energy,
        triggerType=payload.triggerType,
        note=payload.note,
        tagIds=tag_codes,
    )


# --------------------------------------
# Week 4 — Mood Analysis
# --------------------------------------
@router.get(
    "/analysis",
    response_model=MoodAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
def get_analysis(
    range: str = Query("today", regex="^(today|7d|30d)$"),
    supabase=Depends(get_supabase),
    current_user=Depends(get_current_user),
):
    """
    Week 4:
    - range: today | 7d | 30d
    - 분석은 집계 기반 (AI ❌)
    """

    user_id: int = current_user["user_id"]

    try:
        return get_mood_analysis(
            supabase=supabase,
            user_id=user_id,
            range_key=range,
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid range value",
        )
