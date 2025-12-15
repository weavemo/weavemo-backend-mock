# weavemo-backend/services/mood_service.py

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any

from schemas.mood import (
    MoodAnalysisResponse,
    MoodAnalysisSummary,
    MoodAnalysisPoint,
    MoodTagSummaryItem,
    SummaryLabel,
    TodayMoodInfo,
)


# -------------------------
# range → 날짜 범위 계산
# -------------------------
def _resolve_date_range(range_key: str) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()

    if range_key == "today":
        return today, today
    if range_key == "7d":
        return today - timedelta(days=6), today
    if range_key == "30d":
        return today - timedelta(days=29), today

    raise ValueError("Invalid range value")


# -------------------------
# summary label 계산
# -------------------------
def _calc_summary_label(main_valence: int, energy: int) -> SummaryLabel:
    if main_valence == 0:
        return SummaryLabel.NEUTRAL

    if main_valence < 0 and energy <= 2:
        return SummaryLabel.LOW_VALENCE_LOW_ENERGY
    if main_valence < 0 and energy >= 3:
        return SummaryLabel.LOW_VALENCE_HIGH_ENERGY
    if main_valence > 0 and energy <= 2:
        return SummaryLabel.HIGH_VALENCE_LOW_ENERGY
    if main_valence > 0 and energy >= 3:
        return SummaryLabel.HIGH_VALENCE_HIGH_ENERGY

    return SummaryLabel.NEUTRAL


# -------------------------
# main service
# -------------------------
def get_mood_analysis(
    *,
    supabase,
    user_id: int,
    range_key: str,
) -> MoodAnalysisResponse:
    start_date, end_date = _resolve_date_range(range_key)

    # 1️⃣ moods 조회
    moods_res = (
        supabase.table("moods")
        .select("id, date, main_valence, energy, note, trigger_type")
        .eq("user_id", user_id)
        .gte("date", start_date.isoformat())
        .lte("date", end_date.isoformat())
        .order("date", desc=False)
        .execute()
    )

    moods: List[Dict[str, Any]] = moods_res.data or []

    if not moods:
        # 기록 없는 기간
        return MoodAnalysisResponse(
            range=range_key,
            summary=MoodAnalysisSummary(
                mainValence=0,
                energy=0,
                label=SummaryLabel.NEUTRAL,
                hasNote=False,
            ),
            points=[],
            tagsSummary=[],
            todayMood=None,
        )

    # 2️⃣ points 생성 (raw mood = 1 point)
    points = [
        MoodAnalysisPoint(
            date=m["date"],
            mainValence=m["main_valence"],
            energy=m["energy"],
        )
        for m in moods
    ]

    # 3️⃣ summary 계산
    # 기준: 마지막 날짜 mood (today / 기간 마지막)
    base = moods[-1]
    summary = MoodAnalysisSummary(
        mainValence=base["main_valence"],
        energy=base["energy"],
        label=_calc_summary_label(
            base["main_valence"],
            base["energy"],
        ),
        hasNote=bool(base.get("note")),
    )

    # 4️⃣ tags summary
    mood_ids = [m["id"] for m in moods]

    tags_res = (
        supabase.table("mood_emotion_tags")
        .select("emotion_tags(code)")
        .in_("mood_id", mood_ids)
        .execute()
    )

    tag_counts: Dict[str, int] = {}
    for row in tags_res.data or []:
        tag = row.get("emotion_tags")
        if not tag:
            continue
        code = tag["code"]
        tag_counts[code] = tag_counts.get(code, 0) + 1

    tags_summary = [
        MoodTagSummaryItem(code=code, count=count)
        for code, count in tag_counts.items()
    ]

    # 5️⃣ todayMood (today range only)
    today_mood = None
    if range_key == "today":
        today_mood = TodayMoodInfo(
            moodId=base["id"],
            note=base.get("note"),
            triggerType=base.get("trigger_type"),
        )

    return MoodAnalysisResponse(
        range=range_key,
        summary=summary,
        points=points,
        tagsSummary=tags_summary,
        todayMood=today_mood,
    )
