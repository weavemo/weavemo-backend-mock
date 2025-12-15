# routers/mood.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status

from db.database import get_supabase  # Supabase client provider (you said this exists)
from dependencies.auth import get_current_user  # MUST return a user object/dict with internal user_id
from schemas.mood import MoodInput, MoodResult  # request/response schemas (Pydantic)

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
    - 인증: get_current_user
    - 하루 1회 정책: (user_id + UTC date) 기준 upsert
      - 존재하면 update
      - 없으면 insert
      - 응답은 항상 200
    - tags: mood_emotion_tags 를 '전체 삭제 후 재삽입' 방식으로 동기화
    """

    # 0) user_id 확보 (내부 users.id BIGINT 이어야 함)
    #    ※ get_current_user가 이미 내부 user_id를 반환한다고 가정 (프로젝트 표준)
    user_id = current_user["id"] if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 1) 서버 기준 UTC date
    now_utc = datetime.now(timezone.utc)
    today_utc_date = now_utc.date().isoformat()  # 'YYYY-MM-DD'

    # 2) 오늘 mood 존재 여부 조회 (user_id + date)
    existing = (
        supabase.table("moods")
        .select("id")
        .eq("user_id", user_id)
        .eq("date", today_utc_date)
        .limit(1)
        .execute()
    )
    existing_rows = getattr(existing, "data", None) or []
    existing_id: Optional[int] = existing_rows[0]["id"] if len(existing_rows) > 0 else None

    # 3) insert or update payload (DB 컬럼명 기준)
    mood_write: Dict[str, Any] = {
        "main_valence": payload.mainValence,
        "energy": payload.energy,
        "trigger_type": payload.triggerType,
        "note": payload.note,
        # date / recorded_at은 create 시 필수로 넣고,
        # update 시에는 date는 그대로 유지(동일 날짜)하는 게 안전함.
    }

    if existing_id is None:
        # create
        mood_write["user_id"] = user_id
        mood_write["date"] = today_utc_date
        mood_write["recorded_at"] = now_utc.isoformat()

        created = supabase.table("moods").insert(mood_write).execute()
        created_rows = getattr(created, "data", None) or []
        if not created_rows:
            raise HTTPException(status_code=500, detail="Failed to create mood")

        mood_id: int = created_rows[0]["id"]
    else:
        # update
        updated = supabase.table("moods").update(mood_write).eq("id", existing_id).execute()
        updated_rows = getattr(updated, "data", None) or []
        if not updated_rows:
            raise HTTPException(status_code=500, detail="Failed to update mood")

        mood_id = existing_id

    # 4) 태그 동기화: mood_emotion_tags 전체 삭제 후 재삽입
    #    - 프론트 tagIds는 string[] (ex: ["anxious","sad"]) = emotion_tags.code 로 매핑한다고 가정
    tag_codes: List[str] = payload.tagIds or []

    # 4-1) 기존 연결 삭제 (항상 수행)
    supabase.table("mood_emotion_tags").delete().eq("mood_id", mood_id).execute()

    # 4-2) 새 태그가 있으면 emotion_tags.id 조회 → mood_emotion_tags 삽입
    if tag_codes:
        tag_rows_res = supabase.table("emotion_tags").select("id, code").in_("code", tag_codes).execute()
        tag_rows = getattr(tag_rows_res, "data", None) or []

        # 요청한 코드 중 DB에 없는 코드가 있으면 400 (데이터 정합성)
        found_codes = {t["code"] for t in tag_rows}
        missing = [c for c in tag_codes if c not in found_codes]
        if missing:
            raise HTTPException(
                status_code=400,
                detail={"message": "Unknown tag code(s)", "missing": missing},
            )

        join_rows = [{"mood_id": mood_id, "tag_id": t["id"]} for t in tag_rows]
        supabase.table("mood_emotion_tags").insert(join_rows).execute()

    # 5) 응답 (프론트가 최소한으로 필요한 값만)
    return MoodResult(
        moodId=mood_id,
        date=today_utc_date,
        mainValence=payload.mainValence,
        energy=payload.energy,
        triggerType=payload.triggerType,
        note=payload.note,
        tagIds=tag_codes,
    )
