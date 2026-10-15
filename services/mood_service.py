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
    TodayMoodNote,
    MoodTriggerSummaryItem,
    MoodDailyInsight,
    MoodWeeklyInsight,
    MoodPeriodComparison,
    MoodPeriodInsights,
)

# -------------------------
# metrics 怨꾩궛 (Week 9)
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
    # ?됯퇏
    avg_valence = sum(p.mainValence for p in points) / len(points)
    avg_energy = sum(p.energy for p in points) / len(points)

    # ?⑥닚 異붿꽭 (?꾨컲 vs ?꾨컲 ?됯퇏)
    half = len(points) // 2 or 1
    first_half = points[:half]
    second_half = points[half:]

    def _trend(first: List[MoodAnalysisPoint], second: List[MoodAnalysisPoint], key: str):
        # second媛 鍮꾨㈃(?? points 1媛? 異붿꽭??flat?쇰줈 泥섎━
        if not first or not second:
            return "flat"
        f = sum(getattr(p, key) for p in first) / len(first)
        s = sum(getattr(p, key) for p in second) / len(second)
        if s > f + 0.2:
            return "up"
        if s < f - 0.2:
            return "down"
        return "flat"

    valence_trend = _trend(first_half, second_half, "mainValence")
    energy_trend = _trend(first_half, second_half, "energy")

    # 蹂?숈꽦 (range 湲곕컲)
    energies = [p.energy for p in points]
    energy_range = max(energies) - min(energies)
    if energy_range >= 3:
        energy_volatility = "high"
    elif energy_range >= 2:
        energy_volatility = "medium"
    else:
        energy_volatility = "low"

    # 遺꾪룷
    positive_ratio = len([p for p in points if p.mainValence > 0]) / len(points)

    # 吏諛??쒓렇
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
# range ???좎쭨 踰붿쐞 怨꾩궛
# -------------------------



# -------------------------
# summary label 怨꾩궛
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

def _safe_average(
    values: List[float],
) -> float:
    if not values:
        return 0.0

    return round(
        sum(values) / len(values),
        2,
    )


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

    return round(
        positive_count / len(moods),
        2,
    )


def _count_active_days(
    moods: List[Dict[str, Any]],
) -> int:
    return len({
        str(mood["date"])
        for mood in moods
    })


def _build_daily_insights(
    moods: List[Dict[str, Any]],
) -> List[MoodDailyInsight]:
    grouped: Dict[
        str,
        List[Dict[str, Any]],
    ] = {}

    for mood in moods:
        date_key = str(mood["date"])

        grouped.setdefault(
            date_key,
            [],
        ).append(mood)

    insights: List[
        MoodDailyInsight
    ] = []

    for date_key in sorted(grouped):
        day_moods = grouped[date_key]

        note_count = sum(
            1
            for mood in day_moods
            if str(
                mood.get("note") or ""
            ).strip()
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
                checkin_count=len(
                    day_moods
                ),
                note_count=note_count,
                positive_ratio=(
                    _positive_ratio(
                        day_moods
                    )
                ),
            )
        )

    return insights


def _build_weekly_insights(
    moods: List[Dict[str, Any]],
) -> List[MoodWeeklyInsight]:
    grouped: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for mood in moods:
        try:
            mood_date = (
                date.fromisoformat(
                    str(mood["date"])
                )
            )
        except ValueError:
            continue

        week_start = (
            mood_date
            - timedelta(
                days=mood_date.weekday()
            )
        )

        week_end = (
            week_start
            + timedelta(days=6)
        )

        key = week_start.isoformat()

        if key not in grouped:
            grouped[key] = {
                "week_start": (
                    week_start
                ),
                "week_end": week_end,
                "moods": [],
            }

        grouped[key]["moods"].append(
            mood
        )

    insights: List[
        MoodWeeklyInsight
    ] = []

    for key in sorted(grouped):
        group = grouped[key]
        week_moods = group["moods"]

        note_count = sum(
            1
            for mood in week_moods
            if str(
                mood.get("note") or ""
            ).strip()
        )

        insights.append(
            MoodWeeklyInsight(
                week_start=group[
                    "week_start"
                ].isoformat(),
                week_end=group[
                    "week_end"
                ].isoformat(),
                avg_valence=_safe_average([
                    mood["main_valence"]
                    for mood in week_moods
                ]),
                avg_energy=_safe_average([
                    mood["energy"]
                    for mood in week_moods
                ]),
                positive_ratio=(
                    _positive_ratio(
                        week_moods
                    )
                ),
                checkin_count=len(
                    week_moods
                ),
                note_count=note_count,
                active_days=(
                    _count_active_days(
                        week_moods
                    )
                ),
            )
        )

    return insights


def _build_trigger_summary(
    moods: List[Dict[str, Any]],
) -> List[MoodTriggerSummaryItem]:
    counts: Dict[str, int] = {}

    for mood in moods:
        trigger = mood.get(
            "trigger_type"
        )

        if not trigger:
            continue

        counts[trigger] = (
            counts.get(trigger, 0)
            + 1
        )

    return [
        MoodTriggerSummaryItem(
            trigger_type=trigger,
            count=count,
        )
        for trigger, count in sorted(
            counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )
    ]


def _build_period_comparison(
    current_moods: List[
        Dict[str, Any]
    ],
    previous_moods: List[
        Dict[str, Any]
    ],
) -> MoodPeriodComparison:
    if not previous_moods:
        return MoodPeriodComparison(
            previous_available=False
        )

    current_avg_valence = (
        _safe_average([
            mood["main_valence"]
            for mood in current_moods
        ])
    )

    previous_avg_valence = (
        _safe_average([
            mood["main_valence"]
            for mood in previous_moods
        ])
    )

    current_avg_energy = (
        _safe_average([
            mood["energy"]
            for mood in current_moods
        ])
    )

    previous_avg_energy = (
        _safe_average([
            mood["energy"]
            for mood in previous_moods
        ])
    )

    return MoodPeriodComparison(
        previous_available=True,
        avg_valence_delta=round(
            current_avg_valence
            - previous_avg_valence,
            2,
        ),
        avg_energy_delta=round(
            current_avg_energy
            - previous_avg_energy,
            2,
        ),
        positive_ratio_delta=round(
            _positive_ratio(
                current_moods
            )
            - _positive_ratio(
                previous_moods
            ),
            2,
        ),
        checkin_count_delta=(
            len(current_moods)
            - len(previous_moods)
        ),
        active_days_delta=(
            _count_active_days(
                current_moods
            )
            - _count_active_days(
                previous_moods
            )
        ),
    )


def _build_insight_codes(
    *,
    moods: List[Dict[str, Any]],
    total_days: int,
    daily_insights: List[
        MoodDailyInsight
    ],
    comparison: MoodPeriodComparison,
    dominant_trigger: str | None,
) -> List[str]:
    codes: List[str] = []

    active_days = (
        _count_active_days(moods)
    )

    consistency_score = (
        active_days
        / total_days
        * 100
    )

    note_count = sum(
        1
        for mood in moods
        if str(
            mood.get("note") or ""
        ).strip()
    )

    if comparison.previous_available:
        if (
            comparison.avg_valence_delta
            >= 0.2
        ):
            codes.append(
                "VALENCE_IMPROVING"
            )
        elif (
            comparison.avg_valence_delta
            <= -0.2
        ):
            codes.append(
                "VALENCE_DECLINING"
            )
        else:
            codes.append(
                "VALENCE_STABLE"
            )

        if (
            comparison.avg_energy_delta
            >= 0.3
        ):
            codes.append(
                "ENERGY_INCREASING"
            )
        elif (
            comparison.avg_energy_delta
            <= -0.3
        ):
            codes.append(
                "ENERGY_DECREASING"
            )

    current_positive_ratio = (
        _positive_ratio(moods)
    )

    if current_positive_ratio >= 0.6:
        codes.append(
            "POSITIVE_MAJORITY"
        )
    elif current_positive_ratio <= 0.3:
        codes.append(
            "NEGATIVE_MAJORITY"
        )
    else:
        codes.append(
            "EMOTION_BALANCED"
        )

    if consistency_score >= 70:
        codes.append(
            "CHECKIN_CONSISTENT"
        )
    elif consistency_score < 40:
        codes.append(
            "CHECKIN_SPARSE"
        )

    if note_count >= (
        3 if total_days == 7 else 5
    ):
        codes.append(
            "NOTES_ACTIVE"
        )

    if dominant_trigger:
        codes.append(
            "TRIGGER_PATTERN_FOUND"
        )

    if daily_insights:
        daily_values = [
            insight.avg_valence
            for insight in daily_insights
        ]

        if (
            max(daily_values)
            - min(daily_values)
            >= 2
        ):
            codes.append(
                "HIGH_MOOD_VARIABILITY"
            )

    return codes

def _build_advice_codes(
    *,
    moods: List[Dict[str, Any]],
    total_days: int,
    daily_insights: List[
        MoodDailyInsight
    ],
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

    positive_ratio = (
        _positive_ratio(moods)
    )

    active_days = (
        _count_active_days(moods)
    )

    consistency_score = (
        active_days
        / total_days
        * 100
    )

    # 湲곕줉???꾩쭅 遺議깊븳 寃쎌슦
    if consistency_score < 40:
        advice.append(
            "BUILD_CHECKIN_HABIT"
        )

    # ?먮꼫吏媛 ?꾨컲?곸쑝濡???? 寃쎌슦
    if avg_energy <= 2:
        advice.append(
            "REST_PRIORITY"
        )
    elif (
        avg_energy <= 3
        and avg_valence <= 0
    ):
        advice.append(
            "LIGHT_ACTIVITY"
        )

    # 媛먯젙 ?먮뒗 ?먮꼫吏 蹂?붽? ??寃쎌슦
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
            max(valence_values)
            - min(valence_values)
        )

        energy_range = (
            max(energy_values)
            - min(energy_values)
        )

        if (
            valence_range >= 2
            or energy_range >= 2
        ):
            advice.append(
                "TRACK_DAILY_ROUTINE"
            )

    # 諛섎났?섎뒗 媛먯젙 ?먯씤???덈뒗 寃쎌슦
    if dominant_trigger:
        advice.append(
            "REVIEW_DOMINANT_TRIGGER"
        )

    # 遺덊렪??媛먯젙 鍮꾩쨷???믪? 寃쎌슦
    if positive_ratio <= 0.3:
        advice.append(
            "GENTLE_RECOVERY"
        )

    # 湲띿젙?곸씤 ?먮쫫??留롮? 寃쎌슦
    elif positive_ratio >= 0.6:
        advice.append(
            "REPEAT_POSITIVE_PATTERN"
        )

    # ?댁쟾 湲곌컙蹂대떎 媛먯젙怨??먮꼫吏媛 ?④퍡 醫뗭븘吏?寃쎌슦
    if (
        comparison.previous_available
        and comparison.avg_valence_delta
        >= 0.2
        and comparison.avg_energy_delta
        >= 0
    ):
        advice.append(
            "KEEP_CURRENT_ROUTINE"
        )

    # 以묐났 ?쒓굅 ??理쒕? 3媛쒕쭔 ?쒓났
    unique_advice = list(
        dict.fromkeys(advice)
    )

    return unique_advice[:3]

def _build_period_insights(
    *,
    moods: List[Dict[str, Any]],
    previous_moods: List[
        Dict[str, Any]
    ],
    total_days: int,
) -> MoodPeriodInsights:
    daily_insights = (
        _build_daily_insights(moods)
    )

    trigger_summary = (
        _build_trigger_summary(moods)
    )

    comparison = (
        _build_period_comparison(
            moods,
            previous_moods,
        )
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

        strongest_day = (
            strongest.date
        )

        difficult_day = (
            difficult.date
        )

        grouped: Dict[
            str,
            List[Dict[str, Any]],
        ] = {}

        for mood in moods:
            grouped.setdefault(
                str(mood["date"]),
                [],
            ).append(mood)

        variability: Dict[
            str,
            float,
        ] = {}

        for date_key, day_moods in (
            grouped.items()
        ):
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

    active_days = (
        _count_active_days(moods)
    )

    consistency_score = round(
        min(
            100.0,
            active_days
            / total_days
            * 100,
        ),
        1,
    )

    note_count = sum(
        1
        for mood in moods
        if str(
            mood.get("note") or ""
        ).strip()
    )

    return MoodPeriodInsights(
        checkin_count=len(moods),
        active_days=active_days,
        note_count=note_count,
        consistency_score=(
            consistency_score
        ),
        strongest_day=strongest_day,
        difficult_day=difficult_day,
        most_variable_day=(
            most_variable_day
        ),
        dominant_trigger=(
            dominant_trigger
        ),
        trigger_summary=(
            trigger_summary
        ),
        daily_insights=(
            daily_insights
        ),
        weekly_insights=(
            _build_weekly_insights(
                moods
            )
            if total_days == 30
            else []
        ),
        comparison=comparison,
        insight_codes=(
            _build_insight_codes(
                moods=moods,
                total_days=total_days,
                daily_insights=(
                    daily_insights
                ),
                comparison=comparison,
                dominant_trigger=(
                    dominant_trigger
                ),
            )
        ),
        advice_codes=(
            _build_advice_codes(
                moods=moods,
                total_days=total_days,
                daily_insights=(
                    daily_insights
                ),
                comparison=comparison,
                dominant_trigger=(
                    dominant_trigger
                ),
            )
        ),
    )

# -------------------------
# main service
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

    # ??range蹂?湲곌컙: today=?ㅻ뒛 ?섎（, 7d=?ㅻ뒛 ?ы븿 7?? 30d=?ㅻ뒛 ?ы븿 30??    # end_local? "?댁씪 00:00"?쇰줈 怨좎젙?댁빞 (7d/30d?? 湲곌컙 ?앷퉴吏 ?ы븿??
    if range_key == "today":
        start_local = datetime.combine(local_today, datetime.min.time())
    elif range_key == "7d":
        start_local = datetime.combine(local_today - timedelta(days=6), datetime.min.time())
    elif range_key == "30d":
        start_local = datetime.combine(local_today - timedelta(days=29), datetime.min.time())
    else:
        raise ValueError("Invalid range")

   # end_local = datetime.combine(local_today + timedelta(days=1), datetime.min.time())
    # ??end????긽 "?댁씪 00:00 (local)"濡?怨좎젙 (range媛 ?щ씪???ㅻ뒛 ?앷퉴吏 ?ы븿)
    end_local = datetime.combine(local_today + timedelta(days=1), datetime.min.time())

    start_utc = start_local - timedelta(minutes=tz_offset_min)
    end_utc = end_local - timedelta(minutes=tz_offset_min)

    # 1截뤴깵 moods 議고쉶 (?ㅽ듃?뚰겕/Supabase ?ㅻ쪟 ?쒖뿉???붾㈃??二쎌? ?딄쾶 鍮?寃곌낵濡??대갚)
    try:
        moods_res = (
            supabase.table("moods")
            .select("id, date, recorded_at, main_valence, energy, note, trigger_type")
            .eq("user_id", user_id)
            .gte("recorded_at", start_utc.isoformat())
        #    .lte("recorded_at", end_utc.isoformat())
            # ??寃쎄퀎 以묐났/?꾨씫 諛⑹?: end??誘몃쭔(<)??媛???덉쟾
            .lt("recorded_at", end_utc.isoformat())
            .order("recorded_at", desc=False)
            .execute()
        )
    except Exception:
        moods_res = None

    moods: List[Dict[str, Any]] = (moods_res.data if moods_res and getattr(moods_res, "data", None) else []) or []

    previous_moods: List[
        Dict[str, Any]
    ] = []

    period_days = (
        7
        if range_key == "7d"
        else 30
        if range_key == "30d"
        else None
    )

    previous_moods: List[
        Dict[str, Any]
    ] = []

    # today?먯꽌??None,
    # 7d? 30d?먯꽌???꾨옒?먯꽌 遺꾩꽍 寃곌낵瑜??ｌ쓬
    period_insights = None

    if include_period_insights and period_days is not None:
        previous_end_utc = start_utc
        previous_start_utc = (
            previous_end_utc
            - timedelta(
                days=period_days
            )
        )

        try:
            previous_res = (
                supabase.table("moods")
                .select(
                    "id, date, recorded_at, "
                    "main_valence, energy, "
                    "note, trigger_type"
                )
                .eq(
                    "user_id",
                    user_id,
                )
                .gte(
                    "recorded_at",
                    previous_start_utc.isoformat(),
                )
                .lt(
                    "recorded_at",
                    previous_end_utc.isoformat(),
                )
                .order(
                    "recorded_at",
                    desc=False,
                )
                .execute()
            )

            previous_moods = (
                previous_res.data
                if previous_res
                and getattr(
                    previous_res,
                    "data",
                    None,
                )
                else []
            ) or []
        except Exception:
            previous_moods = []

    # 湲곕줉???녿뒗 寃쎌슦
    # today, 7d, 30d 紐⑤몢 ?ш린?먯꽌 泥섎━
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
                if include_period_insights and period_days is not None
                else None
            ),
        )

    # 7?셋?0???꾨Ц 遺꾩꽍
    if include_period_insights and period_days is not None:
        period_insights = (
            _build_period_insights(
                moods=moods,
                previous_moods=previous_moods,
                total_days=period_days,
            )
        )

    # 2截뤴깵 points ?앹꽦 (raw mood = 1 point)
    points = [
        MoodAnalysisPoint(
            date=m["date"],
            mainValence=m["main_valence"],
            energy=m["energy"],
            recordedAt=m.get("recorded_at"),
        )
        for m in moods
    ]

    # 3截뤴깵 summary 怨꾩궛
    # 湲곗?: 留덉?留??좎쭨 mood (today / 湲곌컙 留덉?留?
    base = moods[-1]
    has_note = bool(
        str(base.get("note") or "").strip()
    )
    
    if range_key == "today":
        has_note = any(
            bool(
                str(
                    mood.get("note") or ""
                ).strip()
            )
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

    # 4截뤴깵 tags summary
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

        # supabase join 寃곌낵媛 dict???섎룄, list???섎룄 ?덉뼱??????泥섎━
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

    # 5截뤴깵 todayMood (today range only)
    today_mood = None
    if range_key == "today":
        today_mood = TodayMoodInfo(
            moodId=base["id"],
            note=base.get("note"),
            triggerType=base.get("trigger_type"),
        )

    today_mood_notes: List[
        TodayMoodNote
    ] = []
    
    if range_key == "today":
        today_mood_notes = [
            TodayMoodNote(
                moodId=mood["id"],
                recordedAt=mood.get(
                    "recorded_at"
                ),
                note=str(
                    mood.get("note") or ""
                ).strip(),
                triggerType=mood.get(
                    "trigger_type"
                ),
            )
            for mood in moods
            if str(
                mood.get("note") or ""
            ).strip()
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
        todayMoodNotes=(
            today_mood_notes
        ),
        periodInsights=(
            period_insights
        ),
    )
