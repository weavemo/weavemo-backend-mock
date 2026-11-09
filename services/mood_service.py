# services/mood_service.py

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any

from services.mood_detail_service import (
    build_mood_details,
    build_personal_baseline,
)
from schemas.mood import (
    MoodAnalysisResponse,
    MoodAnalysisSummary,
    MoodAnalysisPoint,
    MoodTagSummaryItem,
    SummaryLabel,
    MoodAnalysisMetrics,
    TodayMoodInfo,
    TodayMoodNote,
    MoodTriggerSummaryItem,
    MoodDailyInsight,
    MoodWeeklyInsight,
    MoodPeriodComparison,
    MoodPeriodInsights,
)


# -------------------------
# 기본 분석 지표 계산
# -------------------------

def _compute_metrics(
    points: List[MoodAnalysisPoint],
    tags_summary: List[MoodTagSummaryItem],
) -> Dict[str, Any]:
    if not points:
        return {
            "avg_valence": 0.0,
            "avg_energy": 0.0,
            "valence_trend": "flat",
            "energy_trend": "flat",
            "energy_volatility": "low",
            "positive_ratio": 0.0,
            "dominant_tags": [
                tag.code for tag in tags_summary[:2]
            ],
        }

    # 전체 기록의 기분과 에너지 평균을 계산한다.
    avg_valence = (
        sum(point.mainValence for point in points)
        / len(points)
    )
    avg_energy = (
        sum(point.energy for point in points)
        / len(points)
    )

    # 시간순 기록을 앞부분과 뒷부분으로 나누어 평균을 비교한다.
    half = len(points) // 2 or 1
    first_half = points[:half]
    second_half = points[half:]

    def _trend(
        first: List[MoodAnalysisPoint],
        second: List[MoodAnalysisPoint],
        key: str,
    ):
        # 비교할 기록이 없으면 변화 없음으로 처리한다.
        if not first or not second:
            return "flat"

        first_average = (
            sum(getattr(point, key) for point in first)
            / len(first)
        )
        second_average = (
            sum(getattr(point, key) for point in second)
            / len(second)
        )

        if second_average > first_average + 0.2:
            return "up"
        if second_average < first_average - 0.2:
            return "down"

        return "flat"

    valence_trend = _trend(
        first_half,
        second_half,
        "mainValence",
    )
    energy_trend = _trend(
        first_half,
        second_half,
        "energy",
    )

    # 에너지의 최댓값과 최솟값 차이로 변동 수준을 구분한다.
    energies = [point.energy for point in points]
    energy_range = max(energies) - min(energies)

    if energy_range >= 3:
        energy_volatility = "high"
    elif energy_range >= 2:
        energy_volatility = "medium"
    else:
        energy_volatility = "low"

    # 전체 기록 중 긍정적인 기분을 기록한 비율이다.
    positive_ratio = (
        sum(point.mainValence > 0 for point in points)
        / len(points)
    )

    # 가장 자주 선택한 감정 태그 두 개를 사용한다.
    dominant_tags = [
        tag.code for tag in tags_summary[:2]
    ]

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
# 기분과 에너지에 따른 요약 분류
# -------------------------

def _calc_summary_label(
    main_valence: int,
    energy: int,
) -> SummaryLabel:
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
# 공통 집계 함수
# -------------------------

def _safe_average(
    values: List[float],
) -> float:
    if not values:
        return 0.0

    return round(sum(values) / len(values), 2)


def _positive_ratio(
    moods: List[Dict[str, Any]],
) -> float:
    if not moods:
        return 0.0

    positive_count = sum(
        1
        for mood in moods
        if mood["main_valence"] > 0
    )

    return round(positive_count / len(moods), 2)


def _count_active_days(
    moods: List[Dict[str, Any]],
) -> int:
    return len({
        str(mood["date"])
        for mood in moods
    })


# -------------------------
# 날짜별 분석
# -------------------------

def _build_daily_insights(
    moods: List[Dict[str, Any]],
) -> List[MoodDailyInsight]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for mood in moods:
        date_key = str(mood["date"])
        grouped.setdefault(date_key, []).append(mood)

    insights: List[MoodDailyInsight] = []

    for date_key in sorted(grouped):
        day_moods = grouped[date_key]

        note_count = sum(
            1
            for mood in day_moods
            if str(mood.get("note") or "").strip()
        )

        insights.append(
            MoodDailyInsight(
                date=date_key,
                avg_valence=_safe_average([
                    mood["main_valence"]
                    for mood in day_moods
                ]),
                avg_energy=_safe_average([
                    mood["energy"]
                    for mood in day_moods
                ]),
                checkin_count=len(day_moods),
                note_count=note_count,
                positive_ratio=_positive_ratio(day_moods),
            )
        )

    return insights


# -------------------------
# 주별 분석
# -------------------------

def _build_weekly_insights(
    moods: List[Dict[str, Any]],
) -> List[MoodWeeklyInsight]:
    grouped: Dict[str, Dict[str, Any]] = {}

    for mood in moods:
        try:
            mood_date = date.fromisoformat(
                str(mood["date"])
            )
        except ValueError:
            continue

        # 월요일부터 일요일까지를 한 주로 묶는다.
        week_start = mood_date - timedelta(
            days=mood_date.weekday()
        )
        week_end = week_start + timedelta(days=6)
        key = week_start.isoformat()

        if key not in grouped:
            grouped[key] = {
                "week_start": week_start,
                "week_end": week_end,
                "moods": [],
            }

        grouped[key]["moods"].append(mood)

    insights: List[MoodWeeklyInsight] = []

    for key in sorted(grouped):
        group = grouped[key]
        week_moods = group["moods"]

        note_count = sum(
            1
            for mood in week_moods
            if str(mood.get("note") or "").strip()
        )

        insights.append(
            MoodWeeklyInsight(
                week_start=group["week_start"].isoformat(),
                week_end=group["week_end"].isoformat(),
                avg_valence=_safe_average([
                    mood["main_valence"]
                    for mood in week_moods
                ]),
                avg_energy=_safe_average([
                    mood["energy"]
                    for mood in week_moods
                ]),
                positive_ratio=_positive_ratio(week_moods),
                checkin_count=len(week_moods),
                note_count=note_count,
                active_days=_count_active_days(week_moods),
            )
        )

    return insights


# -------------------------
# 기존 단일 영향 요인 집계
# -------------------------

def _build_trigger_summary(
    moods: List[Dict[str, Any]],
) -> List[MoodTriggerSummaryItem]:
    counts: Dict[str, int] = {}

    for mood in moods:
        trigger = mood.get("trigger_type")

        if not trigger:
            continue

        counts[trigger] = counts.get(trigger, 0) + 1

    return [
        MoodTriggerSummaryItem(
            trigger_type=trigger,
            count=count,
        )
        for trigger, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


# -------------------------
# 직전 기간과 현재 기간 비교
# -------------------------

def _build_period_comparison(
    current_moods: List[Dict[str, Any]],
    previous_moods: List[Dict[str, Any]],
) -> MoodPeriodComparison:
    if not previous_moods:
        return MoodPeriodComparison(
            previous_available=False
        )

    current_avg_valence = _safe_average([
        mood["main_valence"]
        for mood in current_moods
    ])
    previous_avg_valence = _safe_average([
        mood["main_valence"]
        for mood in previous_moods
    ])

    current_avg_energy = _safe_average([
        mood["energy"]
        for mood in current_moods
    ])
    previous_avg_energy = _safe_average([
        mood["energy"]
        for mood in previous_moods
    ])

    return MoodPeriodComparison(
        previous_available=True,
        avg_valence_delta=round(
            current_avg_valence - previous_avg_valence,
            2,
        ),
        avg_energy_delta=round(
            current_avg_energy - previous_avg_energy,
            2,
        ),
        positive_ratio_delta=round(
            _positive_ratio(current_moods)
            - _positive_ratio(previous_moods),
            2,
        ),
        checkin_count_delta=(
            len(current_moods) - len(previous_moods)
        ),
        active_days_delta=(
            _count_active_days(current_moods)
            - _count_active_days(previous_moods)
        ),
    )


# -------------------------
# 기간 분석 결과 코드 생성
# -------------------------

def _build_insight_codes(
    *,
    moods: List[Dict[str, Any]],
    total_days: int,
    daily_insights: List[MoodDailyInsight],
    comparison: MoodPeriodComparison,
    dominant_trigger: str | None,
) -> List[str]:
    codes: List[str] = []

    active_days = _count_active_days(moods)
    consistency_score = active_days / total_days * 100

    note_count = sum(
        1
        for mood in moods
        if str(mood.get("note") or "").strip()
    )

    if comparison.previous_available:
        if comparison.avg_valence_delta >= 0.2:
            codes.append("VALENCE_IMPROVING")
        elif comparison.avg_valence_delta <= -0.2:
            codes.append("VALENCE_DECLINING")
        else:
            codes.append("VALENCE_STABLE")

        if comparison.avg_energy_delta >= 0.3:
            codes.append("ENERGY_INCREASING")
        elif comparison.avg_energy_delta <= -0.3:
            codes.append("ENERGY_DECREASING")

    current_positive_ratio = _positive_ratio(moods)

    # 중립 기록을 부정 기록으로 분류하지 않도록 따로 계산한다.
    negative_ratio = (
        sum(
            mood["main_valence"] < 0
            for mood in moods
        ) / len(moods)
        if moods
        else 0.0
    )

    if current_positive_ratio >= 0.6:
        codes.append("POSITIVE_MAJORITY")
    elif negative_ratio >= 0.6:
        codes.append("NEGATIVE_MAJORITY")
    else:
        codes.append("EMOTION_BALANCED")

    if consistency_score >= 70:
        codes.append("CHECKIN_CONSISTENT")
    elif consistency_score < 40:
        codes.append("CHECKIN_SPARSE")

    if note_count >= (3 if total_days == 7 else 5):
        codes.append("NOTES_ACTIVE")

    if dominant_trigger:
        codes.append("TRIGGER_PATTERN_FOUND")

    if daily_insights:
        daily_values = [
            insight.avg_valence
            for insight in daily_insights
        ]

        if max(daily_values) - min(daily_values) >= 2:
            codes.append("HIGH_MOOD_VARIABILITY")

    return codes


# -------------------------
# 기간별 행동 제안 코드 생성
# -------------------------

def _build_advice_codes(
    *,
    moods: List[Dict[str, Any]],
    total_days: int,
    daily_insights: List[MoodDailyInsight],
    comparison: MoodPeriodComparison,
    dominant_trigger: str | None,
) -> List[str]:
    advice: List[str] = []

    if not moods:
        return advice

    avg_valence = _safe_average([
        mood["main_valence"]
        for mood in moods
    ])
    avg_energy = _safe_average([
        mood["energy"]
        for mood in moods
    ])
    positive_ratio = _positive_ratio(moods)
    active_days = _count_active_days(moods)
    consistency_score = active_days / total_days * 100

    # 기록한 날짜의 비율이 낮으면 기록 습관을 제안한다.
    if consistency_score < 40:
        advice.append("BUILD_CHECKIN_HABIT")

    # 평균 에너지가 낮으면 휴식을 우선 제안한다.
    if avg_energy <= 2:
        advice.append("REST_PRIORITY")
    elif avg_energy <= 3 and avg_valence <= 0:
        advice.append("LIGHT_ACTIVITY")

    # 날짜별 기분 또는 에너지 차이가 크면 일상 흐름 점검을 제안한다.
    if daily_insights:
        valence_values = [
            item.avg_valence
            for item in daily_insights
        ]
        energy_values = [
            item.avg_energy
            for item in daily_insights
        ]

        valence_range = (
            max(valence_values) - min(valence_values)
        )
        energy_range = (
            max(energy_values) - min(energy_values)
        )

        if valence_range >= 2 or energy_range >= 2:
            advice.append("TRACK_DAILY_ROUTINE")

    # 가장 자주 선택한 영향 요인을 돌아보도록 제안한다.
    if dominant_trigger:
        advice.append("REVIEW_DOMINANT_TRIGGER")

    # 기존 제안 기준: 긍정 기록 비율이 낮으면 부드러운 회복 활동을 제안한다.
    if positive_ratio <= 0.3:
        advice.append("GENTLE_RECOVERY")

    # 긍정 기록 비율이 높으면 도움이 된 흐름을 이어가도록 제안한다.
    elif positive_ratio >= 0.6:
        advice.append("REPEAT_POSITIVE_PATTERN")

    # 이전 기간보다 기분 평균이 높아지고 에너지 평균이 낮아지지 않은 경우다.
    if (
        comparison.previous_available
        and comparison.avg_valence_delta >= 0.2
        and comparison.avg_energy_delta >= 0
    ):
        advice.append("KEEP_CURRENT_ROUTINE")

    # 순서를 유지하면서 중복을 제거하고 최대 세 개를 반환한다.
    unique_advice = list(dict.fromkeys(advice))

    return unique_advice[:3]


# -------------------------
# 기간별 분석 결과 구성
# -------------------------

def _build_period_insights(
    *,
    moods: List[Dict[str, Any]],
    previous_moods: List[Dict[str, Any]],
    total_days: int,
) -> MoodPeriodInsights:
    daily_insights = _build_daily_insights(moods)
    trigger_summary = _build_trigger_summary(moods)
    comparison = _build_period_comparison(
        moods,
        previous_moods,
    )

    strongest_day = None
    difficult_day = None
    most_variable_day = None

    if daily_insights:
        strongest = max(
            daily_insights,
            key=lambda item: (
                item.avg_valence,
                item.avg_energy,
            ),
        )
        difficult = min(
            daily_insights,
            key=lambda item: (
                item.avg_valence,
                item.avg_energy,
            ),
        )

        strongest_day = strongest.date
        difficult_day = difficult.date

        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for mood in moods:
            grouped.setdefault(
                str(mood["date"]),
                [],
            ).append(mood)

        variability: Dict[str, float] = {}

        for date_key, day_moods in grouped.items():
            valences = [
                mood["main_valence"]
                for mood in day_moods
            ]
            energies = [
                mood["energy"]
                for mood in day_moods
            ]

            variability[date_key] = (
                max(valences)
                - min(valences)
                + max(energies)
                - min(energies)
            )

        most_variable_day = max(
            variability,
            key=variability.get,
        )

    dominant_trigger = (
        trigger_summary[0].trigger_type
        if trigger_summary
        else None
    )

    active_days = _count_active_days(moods)
    consistency_score = round(
        min(100.0, active_days / total_days * 100),
        1,
    )

    note_count = sum(
        1
        for mood in moods
        if str(mood.get("note") or "").strip()
    )

    return MoodPeriodInsights(
        checkin_count=len(moods),
        active_days=active_days,
        note_count=note_count,
        consistency_score=consistency_score,
        strongest_day=strongest_day,
        difficult_day=difficult_day,
        most_variable_day=most_variable_day,
        dominant_trigger=dominant_trigger,
        trigger_summary=trigger_summary,
        daily_insights=daily_insights,
        weekly_insights=(
            _build_weekly_insights(moods)
            if total_days == 30
            else []
        ),
        comparison=comparison,
        insight_codes=_build_insight_codes(
            moods=moods,
            total_days=total_days,
            daily_insights=daily_insights,
            comparison=comparison,
            dominant_trigger=dominant_trigger,
        ),
        advice_codes=_build_advice_codes(
            moods=moods,
            total_days=total_days,
            daily_insights=daily_insights,
            comparison=comparison,
            dominant_trigger=dominant_trigger,
        ),
    )


# -------------------------
# 감정 분석 조회 및 응답 생성
# -------------------------

def get_mood_analysis(
    *,
    supabase,
    user_id: int,
    range_key: str,
    tz_offset_min: int,
    include_period_insights: bool = False,
) -> MoodAnalysisResponse:
    utc_now = datetime.utcnow()
    local_now = utc_now + timedelta(minutes=tz_offset_min)
    local_today = local_now.date()

    # 오늘, 오늘을 포함한 최근 7일 또는 최근 30일의 시작 시각이다.
    if range_key == "today":
        start_local = datetime.combine(
            local_today,
            datetime.min.time(),
        )
    elif range_key == "7d":
        start_local = datetime.combine(
            local_today - timedelta(days=6),
            datetime.min.time(),
        )
    elif range_key == "30d":
        start_local = datetime.combine(
            local_today - timedelta(days=29),
            datetime.min.time(),
        )
    else:
        raise ValueError("Invalid range")

    # 모든 조회 범위의 끝은 사용자 현지 시각 기준 다음 날 자정이다.
    end_local = datetime.combine(
        local_today + timedelta(days=1),
        datetime.min.time(),
    )

    start_utc = start_local - timedelta(
        minutes=tz_offset_min
    )
    end_utc = end_local - timedelta(
        minutes=tz_offset_min
    )

    # 기존 처리 방식: 조회 실패 시 빈 기록으로 처리한다.
    try:
        moods_res = (
            supabase.table("moods")
            .select(
                "id, date, recorded_at, "
                "main_valence, energy, note, trigger_type"
            )
            .eq("user_id", user_id)
            .gte("recorded_at", start_utc.isoformat())
            # 다음 날 자정은 포함하지 않아 조회 경계의 중복을 방지한다.
            .lt("recorded_at", end_utc.isoformat())
            .order("recorded_at", desc=False)
            .execute()
        )
    except Exception:
        moods_res = None

    moods: List[Dict[str, Any]] = (
        moods_res.data
        if moods_res and getattr(moods_res, "data", None)
        else []
    ) or []

    previous_moods: List[Dict[str, Any]] = []

    period_days = (
        7
        if range_key == "7d"
        else 30
        if range_key == "30d"
        else None
    )

    previous_moods: List[Dict[str, Any]] = []

    # 오늘 분석에는 기간 분석을 넣지 않는다.
    # 7일 또는 30일 분석에서 허용된 경우에만 기간 분석을 생성한다.
    period_insights = None

    if include_period_insights and period_days is not None:
        previous_end_utc = start_utc
        previous_start_utc = (
            previous_end_utc
            - timedelta(days=period_days)
        )

        try:
            previous_res = (
                supabase.table("moods")
                .select(
                    "id, date, recorded_at, "
                    "main_valence, energy, "
                    "note, trigger_type"
                )
                .eq("user_id", user_id)
                .gte(
                    "recorded_at",
                    previous_start_utc.isoformat(),
                )
                .lt(
                    "recorded_at",
                    previous_end_utc.isoformat(),
                )
                .order("recorded_at", desc=False)
                .execute()
            )

            previous_moods = (
                previous_res.data
                if previous_res
                and getattr(previous_res, "data", None)
                else []
            ) or []
        except Exception:
            previous_moods = []

    # 조회 범위에 기록이 없으면 빈 분석 결과를 반환한다.
    if not moods:
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
            todayMoodNotes=[],
            periodInsights=(
                MoodPeriodInsights()
                if include_period_insights
                and period_days is not None
                else None
            ),
        )

    # 허용된 7일 또는 30일 분석의 기간별 결과를 생성한다.
    if include_period_insights and period_days is not None:
        period_insights = _build_period_insights(
            moods=moods,
            previous_moods=previous_moods,
            total_days=period_days,
        )

    # 감정 기록 한 건을 그래프의 점 하나로 변환한다.
    points = [
        MoodAnalysisPoint(
            date=mood["date"],
            mainValence=mood["main_valence"],
            energy=mood["energy"],
            recordedAt=mood.get("recorded_at"),
        )
        for mood in moods
    ]

    # 기존 요약은 조회 범위의 마지막 기록을 기준으로 유지한다.
    base = moods[-1]
    has_note = bool(
        str(base.get("note") or "").strip()
    )

    # 오늘 분석에서는 오늘 작성한 메모가 하나라도 있는지 확인한다.
    if range_key == "today":
        has_note = any(
            bool(str(mood.get("note") or "").strip())
            for mood in moods
        )

    summary = MoodAnalysisSummary(
        mainValence=base["main_valence"],
        energy=base["energy"],
        label=_calc_summary_label(
            base["main_valence"],
            base["energy"],
        ),
        hasNote=has_note,
    )

    # 감정별 집계와 상세 분석에 사용할 감정 태그 및 강도를 조회한다.
    mood_ids = [mood["id"] for mood in moods]

    tags_res = (
        supabase.table("mood_emotion_tags")
        .select("mood_id, intensity, emotion_tags(code)")
        .in_("mood_id", mood_ids)
        .execute()
    )

    # 각 기록에서 선택한 복수 영향 요인을 조회한다.
    trigger_res = (
        supabase.table("mood_triggers")
        .select("mood_id, trigger_type")
        .in_("mood_id", mood_ids)
        .execute()
    )

    # 감정 강도, 감정 조합, 영향 요인 및 오늘의 변화를 계산한다.
    detailed_insights = build_mood_details(
        moods=moods,
        emotion_rows=tags_res.data or [],
        trigger_rows=trigger_res.data or [],
        range_key=range_key,
    )

    # 오늘 분석과 기존에 허용된 기간 분석에 개인 기준선을 연결한다.
    if (
        detailed_insights is not None
        and (
            range_key == "today"
            or include_period_insights
        )
    ):
        baseline_start_utc = (
            start_utc - timedelta(days=14)
        )

        try:
            baseline_moods = []
            batch_size = 500
            offset = 0

            # 서버의 기본 반환 건수 제한으로 기록이 누락되지 않도록 나누어 조회한다.
            while True:
                baseline_res = (
                    supabase.table("moods")
                    .select(
                        "id, recorded_at, main_valence, energy"
                    )
                    .eq("user_id", user_id)
                    .gte(
                        "recorded_at",
                        baseline_start_utc.isoformat(),
                    )
                    .lt(
                        "recorded_at",
                        start_utc.isoformat(),
                    )
                    .order("recorded_at", desc=False)
                    .order("id", desc=False)
                    .range(
                        offset,
                        offset + batch_size - 1,
                    )
                    .execute()
                )

                batch = baseline_res.data or []
                baseline_moods.extend(batch)

                if len(batch) < batch_size:
                    break

                offset += batch_size

            detailed_insights.baseline = (
                build_personal_baseline(
                    current_moods=moods,
                    baseline_moods=baseline_moods,
                    tz_offset_min=tz_offset_min,
                )
            )
        except Exception:
            # 기준선 조회 실패가 현재 기록의 분석까지 막지 않도록 한다.
            # 기존 기본값인 unavailable을 유지한다.
            pass    

    # 기존 화면에서 사용하는 감정 태그별 횟수 집계를 유지한다.
    tag_counts: Dict[str, int] = {}

    for row in tags_res.data or []:
        tag_obj = row.get("emotion_tags")

        if not tag_obj:
            continue

        # 연결 조회 결과가 목록 또는 객체인 경우를 모두 처리한다.
        if isinstance(tag_obj, list):
            for tag in tag_obj:
                code = (
                    tag.get("code")
                    if isinstance(tag, dict)
                    else None
                )

                if not code:
                    continue

                tag_counts[code] = (
                    tag_counts.get(code, 0) + 1
                )

        elif isinstance(tag_obj, dict):
            code = tag_obj.get("code")

            if not code:
                continue

            tag_counts[code] = (
                tag_counts.get(code, 0) + 1
            )

    tags_summary = [
        MoodTagSummaryItem(
            code=code,
            count=count,
        )
        for code, count in sorted(
            tag_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    # 오늘 분석에서만 마지막 감정 기록의 상세 정보를 제공한다.
    today_mood = None

    if range_key == "today":
        today_mood = TodayMoodInfo(
            moodId=base["id"],
            note=base.get("note"),
            triggerType=base.get("trigger_type"),
        )

    # 오늘 작성한 메모를 기록 시간순으로 제공한다.
    today_mood_notes: List[TodayMoodNote] = []

    if range_key == "today":
        today_mood_notes = [
            TodayMoodNote(
                moodId=mood["id"],
                recordedAt=mood.get("recorded_at"),
                note=str(mood.get("note") or "").strip(),
                triggerType=mood.get("trigger_type"),
            )
            for mood in moods
            if str(mood.get("note") or "").strip()
        ]

    return MoodAnalysisResponse(
        range=range_key,
        summary=summary,
        points=points,
        tagsSummary=tags_summary,
        metrics=_compute_metrics(
            points,
            tags_summary,
        ),
        todayMood=today_mood,
        todayMoodNotes=today_mood_notes,
        periodInsights=period_insights,
        detailedInsights=detailed_insights,
    )
