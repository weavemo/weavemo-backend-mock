# weavemo-backend/routers/mood.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status

from db.database import get_supabase
from dependencies.auth import get_current_user
from schemas.mood import MoodInput, MoodResult

router = APIRouter(prefix="/mood", tags=["mood"])


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

    # 2️⃣ 오늘 mood 조회
    existing = (
        supabase.table("moods")
        .select("id")
        .eq("user_id", user_id)
        .eq("date", today)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    existing_id: Optional[int] = rows[0]["id"] if rows else None

    # 3️⃣ 공통 payload
    mood_write: Dict[str, Any] = {
        "main_valence": payload.mainValence,
        "energy": payload.energy,
        "trigger_type": payload.triggerType,
        "note": payload.note,
    }

    if existing_id is None:
        mood_write.update({
            "user_id": user_id,
            "date": today,
            "recorded_at": now_utc.isoformat(),
        })
        created = supabase.table("moods").insert(mood_write).execute()
        mood_id = created.data[0]["id"]
    else:
        supabase.table("moods").update(mood_write).eq("id", existing_id).execute()
        mood_id = existing_id

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
