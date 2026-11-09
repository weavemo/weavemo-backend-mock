# services/mood_detail_service.py

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from schemas.mood import (
    MoodDetailedInsights,
    MoodEmotionDetail,
    MoodEmotionPair,
    MoodEvidenceInsight,
    MoodObservation,
    MoodPersonalBaseline,
    MoodTriggerDetail,
    MoodWithinDayChange,
)


def _average(values):
    return round(sum(values) / len(values), 2)


def _emotion_codes(row):
    joined = row.get("emotion_tags")
    items = joined if isinstance(joined, list) else [joined]

    return {
        item["code"]
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("code"), str)
        and item["code"]
    }


def build_mood_details(
    *,
    moods,
    emotion_rows,
    trigger_rows,
    range_key,
):
    if not moods:
        return None

    mood_by_id = {
        int(mood["id"]): mood
        for mood in moods
    }

    # mood_id     # 각 기록 안에서 같은 감정의 중복을 제거한다.
    emotions_by_mood = defaultdict(dict)

    for row in emotion_rows:
        mood_id = row.get("mood_id")

        if mood_id is None or int(mood_id) not in mood_by_id:
            continue

        mood_id = int(mood_id)
        intensity = row.get("intensity")

        if type(intensity) is not int or not 1 <= intensity <= 5:
            intensity = None

        for code in _emotion_codes(row):
            existing = emotions_by_mood[mood_id].get(code)

            if existing is None or intensity is not None:
                emotions_by_mood[mood_id][code] = intensity

    emotion_counts = Counter()
    intensity_values = defaultdict(list)
    pair_counts = Counter()

    for selected in emotions_by_mood.values():
        codes = sorted(selected)
        emotion_counts.update(codes)
        pair_counts.update(combinations(codes, 2))

        for code, intensity in selected.items():
            if intensity is not None:
                intensity_values[code].append(intensity)

    emotions = [
        MoodEmotionDetail(
            code=code,
            count=count,
            intensity_count=len(intensity_values[code]),
            average_intensity=(
                _average(intensity_values[code])
                if intensity_values[code]
                else None
            ),
        )
        for code, count in sorted(
            emotion_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]

    emotion_pairs = [
        MoodEmotionPair(
            codes=list(pair),
            count=count,
        )
        for pair, count in sorted(
            pair_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]

    # 복수 영향 요인을 우선하고, 과거 단일 필드는 보완용으로 사용한다.
    triggers_by_mood = defaultdict(set)

    for row in trigger_rows:
        mood_id = row.get("mood_id")
        code = row.get("trigger_type")

        if (
            mood_id is not None
            and int(mood_id) in mood_by_id
            and isinstance(code, str)
            and code
        ):
            triggers_by_mood[int(mood_id)].add(code)

    for mood_id, mood in mood_by_id.items():
        legacy_code = mood.get("trigger_type")

        if not triggers_by_mood[mood_id] and legacy_code:
            triggers_by_mood[mood_id].add(legacy_code)

    trigger_moods = defaultdict(list)

    for mood_id, codes in triggers_by_mood.items():
        for code in codes:
            trigger_moods[code].append(mood_by_id[mood_id])

    triggers = [
        MoodTriggerDetail(
            code=code,
            count=len(selected),
            avg_valence=_average([
                mood["main_valence"]
                for mood in selected
            ]),
            avg_energy=_average([
                mood["energy"]
                for mood in selected
            ]),
        )
        for code, selected in sorted(
            trigger_moods.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
    ]

    latest = moods[-1]
    active_days = len({str(mood["date"]) for mood in moods})

    observation = MoodObservation(
        checkin_count=len(moods),
        active_days=active_days,
        avg_valence=_average([
            mood["main_valence"]
            for mood in moods
        ]),
        avg_energy=_average([
            mood["energy"]
            for mood in moods
        ]),
        positive_count=sum(
            mood["main_valence"] > 0 for mood in moods
        ),
        neutral_count=sum(
            mood["main_valence"] == 0 for mood in moods
        ),
        negative_count=sum(
            mood["main_valence"] < 0 for mood in moods
        ),
        latest_valence=latest["main_valence"],
        latest_energy=latest["energy"],
    )

    within_day_change = MoodWithinDayChange()

    if range_key == "today":
        first = moods[0]
        available = (
            len(moods) >= 2
            and bool(first.get("recorded_at"))
            and bool(latest.get("recorded_at"))
            and first["recorded_at"] != latest["recorded_at"]
        )

        within_day_change = MoodWithinDayChange(
            available=available,
            checkin_count=len(moods),
            first_recorded_at=first.get("recorded_at"),
            last_recorded_at=latest.get("recorded_at"),
            valence_delta=(
                latest["main_valence"] - first["main_valence"]
                if available else None
            ),
            energy_delta=(
                latest["energy"] - first["energy"]
                if available else None
            ),
        )

    insights = []

    # 특정 감정을 단정하지 않고 기분·에너지 조합만 구분한다.
    valence_code = (
        "POSITIVE" if latest["main_valence"] > 0
        else "NEGATIVE" if latest["main_valence"] < 0
        else "NEUTRAL"
    )
    energy_code = (
        "LOW" if latest["energy"] <= 2
        else "HIGH" if latest["energy"] >= 4
        else "MID"
    )

    insights.append(
        MoodEvidenceInsight(
            code=f"LATEST_{valence_code}_{energy_code}_ENERGY",
            evidence_count=1,
            evidence_days=1,
            emotion_codes=sorted(
                emotions_by_mood.get(int(latest["id"]), {})
            ),
            trigger_codes=sorted(
                triggers_by_mood.get(int(latest["id"]), set())
            ),
        )
    )

    if within_day_change.available:
        insights.append(
            MoodEvidenceInsight(
                code="TODAY_FIRST_TO_LATEST",
                evidence_count=len(moods),
                evidence_days=1,
            )
        )

    return MoodDetailedInsights(
        observation=observation,
        emotions=emotions,
        emotion_pairs=emotion_pairs,
        triggers=triggers,
        within_day_change=within_day_change,
        # 개인 기준선 조회는 다음 단계에서 연결한다.
        baseline=MoodPersonalBaseline(status="unavailable"),
        insights=insights,
    )

def _local_daily_averages(moods, tz_offset_min):
    grouped = defaultdict(list)

    for mood in moods:
        recorded_at = mood.get("recorded_at")

        if not recorded_at:
            continue

        try:
            timestamp = datetime.fromisoformat(
                str(recorded_at).replace("Z", "+00:00")
            )

            # 시간대 정보가 없는 저장 시각은 UTC로 해석한다.
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(
                    tzinfo=timezone.utc
                )

            local_timestamp = (
                timestamp.astimezone(timezone.utc)
                + timedelta(minutes=tz_offset_min)
            )
            date_key = local_timestamp.date().isoformat()
        except (ValueError, TypeError):
            continue

        grouped[date_key].append(mood)

    return [
        {
            "date": date_key,
            "valence": sum(
                mood["main_valence"]
                for mood in selected
            ) / len(selected),
            "energy": sum(
                mood["energy"]
                for mood in selected
            ) / len(selected),
            "count": len(selected),
        }
        for date_key, selected in sorted(grouped.items())
    ]


def build_personal_baseline(
    *,
    current_moods,
    baseline_moods,
    tz_offset_min,
):
    baseline_days = _local_daily_averages(
        baseline_moods,
        tz_offset_min,
    )
    current_days = _local_daily_averages(
        current_moods,
        tz_offset_min,
    )

    checkin_count = sum(
        item["count"]
        for item in baseline_days
    )
    active_days = len(baseline_days)

      # 초기 제품 기준으로 비교에는 최소 5일의 기록을 사용한다.
    if active_days < 5 or not current_days:
        return MoodPersonalBaseline(
            status="insufficient",
            window_days=14,
            checkin_count=checkin_count,
            active_days=active_days,
        )

    # 반올림 전 값으로 차이를 계산하고, 응답 값만 소수 둘째 자리로 반올림한다.
    baseline_valence = (
        sum(item["valence"] for item in baseline_days)
        / active_days
    )
    baseline_energy = (
        sum(item["energy"] for item in baseline_days)
        / active_days
    )

    current_valence = (
        sum(item["valence"] for item in current_days)
        / len(current_days)
    )
    current_energy = (
        sum(item["energy"] for item in current_days)
        / len(current_days)
    )

    return MoodPersonalBaseline(
        status="available",
        window_days=14,
        checkin_count=checkin_count,
        active_days=active_days,
        avg_valence=round(baseline_valence, 2),
        avg_energy=round(baseline_energy, 2),
        valence_delta=round(
            current_valence - baseline_valence,
            2,
        ),
        energy_delta=round(
            current_energy - baseline_energy,
            2,
        ),
    )
