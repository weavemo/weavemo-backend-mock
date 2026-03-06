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
    MoodAnalysisMetrics,
    TodayMoodInfo,
)

# -------------------------
# metrics 계산 (Week 9)
# -------------------------
def _compute_metrics(points: List[MoodAnalysisPoint], tags_summary: List[MoodTagSummaryItem]) -> Dict[str, Any]:
    if not points:
        return {
            "avg_valence": 0.0,
            "avg_energy": 0.0,
            "valence_trend": "flat",
            "energy_trend": "flat",
            "energy_volatility": "low",
            "positive_ratio": 0.0,
            "dominant_tags": [t.code for t in tags_summary[:2]],
        }
    # 평균
    avg_valence = sum(p.mainValence for p in points) / len(points)
    avg_energy = sum(p.energy for p in points) / len(points)

    # 단순 추세 (전반 vs 후반 평균)
    half = len(points) // 2 or 1
    first_half = points[:half]
    second_half = points[half:]

    def _trend(first: List[MoodAnalysisPoint], second: List[MoodAnalysisPoint], key: str):
        # second가 비면(예: points 1개) 추세는 flat으로 처리
        if not first or not second:
            return "flat"
        f = sum(getattr(p, key) for p in first) / len(first)
        s = sum(getattr(p, key) for p in second) / len(second)        if s > f + 0.2:
            return "up"
        if s < f - 0.2:
            return "down"
        return "flat"

    valence_trend = _trend(first_half, second_half, "mainValence")
    energy_trend = _trend(first_half, second_half, "energy")

    # 변동성 (range 기반)
    energies = [p.energy for p in points]
    energy_range = max(energies) - min(energies)
    if energy_range >= 3:
        energy_volatility = "high"
    elif energy_range >= 2:
        energy_volatility = "medium"
    else:
        energy_volatility = "low"

    # 분포
    positive_ratio = len([p for p in points if p.mainValence > 0]) / len(points)

    # 지배 태그
    dominant_tags = [t.code for t in tags_summary[:2]]

    return {
        "avg_valence": round(avg_valence, 2),
        "avg_energy": round(avg_energy, 2),
        "valence_trend": valence_trend,
        "energy_trend": energy_trend,
        "energy_volatility": energy_volatility,
        "positive_ratio": round(positive_ratio, 2),
        "dominant_tags": dominant_tags,
    }

# -------------------------
# range → 날짜 범위 계산
# -------------------------



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
    tz_offset_min: int,
) -> MoodAnalysisResponse:
    utc_now = datetime.utcnow()
    local_now = utc_now + timedelta(minutes=tz_offset_min)
    local_today = local_now.date()

    # ✅ range별 기간: today=오늘 하루, 7d=오늘 포함 7일, 30d=오늘 포함 30일
    # end_local은 "내일 00:00"으로 고정해야 (7d/30d도) 기간 끝까지 포함됨.
    if range_key == "today":
        start_local = datetime.combine(local_today, datetime.min.time())
    elif range_key == "7d":
        start_local = datetime.combine(local_today - timedelta(days=6), datetime.min.time())
    elif range_key == "30d":
        start_local = datetime.combine(local_today - timedelta(days=29), datetime.min.time())
    else:
        raise ValueError("Invalid range")

   # end_local = datetime.combine(local_today + timedelta(days=1), datetime.min.time())
    # ✅ end는 항상 "내일 00:00 (local)"로 고정 (range가 달라도 오늘 끝까지 포함)
    end_local = datetime.combine(local_today + timedelta(days=1), datetime.min.time())

    start_utc = start_local - timedelta(minutes=tz_offset_min)
    end_utc = end_local - timedelta(minutes=tz_offset_min)

    # 1️⃣ moods 조회 (네트워크/Supabase 오류 시에도 화면이 죽지 않게 빈 결과로 폴백)
    try:
        moods_res = (
            supabase.table("moods")
            .select("id, date, recorded_at, main_valence, energy, note, trigger_type")
            .eq("user_id", user_id)
            .gte("recorded_at", start_utc.isoformat())
        #    .lte("recorded_at", end_utc.isoformat())
            # ✅ 경계 중복/누락 방지: end는 미만(<)이 가장 안전
            .lt("recorded_at", end_utc.isoformat())
            .order("recorded_at", desc=False)
            .execute()
        )
    except Exception:
        moods_res = None

    moods: List[Dict[str, Any]] = (moods_res.data if moods_res and getattr(moods_res, "data", None) else []) or []


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
            metrics=MoodAnalysisMetrics(
                avg_valence=0.0,
                avg_energy=0.0,
                valence_trend="flat",
                energy_trend="flat",
                energy_volatility="low",
                positive_ratio=0.0,
                dominant_tags=[],
            ),
            todayMood=None,
        )

    # 2️⃣ points 생성 (raw mood = 1 point)
    points = [
        MoodAnalysisPoint(
            date=m["date"],
            mainValence=m["main_valence"],
            energy=m["energy"],
            recordedAt=m.get("recorded_at"),
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
        tag_obj = row.get("emotion_tags")
        if not tag_obj:
            continue

        # supabase join 결과가 dict일 수도, list일 수도 있어서 둘 다 처리
        if isinstance(tag_obj, list):
            for t in tag_obj:
                code = t.get("code") if isinstance(t, dict) else None
                if not code:
                    continue
                tag_counts[code] = tag_counts.get(code, 0) + 1
        elif isinstance(tag_obj, dict):
            code = tag_obj.get("code")
            if not code:
                continue
            tag_counts[code] = tag_counts.get(code, 0) + 1

    tags_summary = [
        MoodTagSummaryItem(code=code, count=count)
        for code, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
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
        metrics=_compute_metrics(points, tags_summary),
        todayMood=today_mood,
    )
