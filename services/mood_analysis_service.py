# services/mood_analysis_service.py

from typing import Dict, List

from schemas.mood import MoodAnalysisResponse


def build_reflection_analysis(
    analysis: MoodAnalysisResponse,
) -> Dict[str, List[str]]:
    points = analysis.points

    if not points:
        return {
            "summary": [],
            "reflection_questions": [],
        }

    summary: List[str] = []
    questions: List[str] = []

    positive_count = sum(
        1 for point in points
        if point.mainValence > 0
    )
    negative_count = sum(
        1 for point in points
        if point.mainValence < 0
    )

    positive_ratio = positive_count / len(points)
    negative_ratio = negative_count / len(points)
    avg_energy = analysis.metrics.avg_energy

    if positive_ratio >= 0.65:
        summary.append(
            "오늘 기록에서는 긍정적인 감정이 비교적 자주 나타났어요."
        )
    elif negative_ratio >= 0.65:
        summary.append(
            "오늘 기록에서는 불편한 감정이 비교적 자주 나타났어요."
        )
    elif positive_count > 0 and negative_count > 0:
        summary.append(
            "오늘 기록에는 긍정적인 감정과 불편한 감정이 함께 나타났어요."
        )
    else:
        summary.append(
            "오늘 기록에서는 중립적인 감정을 포함한 흐름이 나타났어요."
        )

    if avg_energy <= 2:
        summary.append(
            "기록된 평균 에너지는 낮은 편이었어요."
        )
    elif avg_energy >= 4:
        summary.append(
            "기록된 평균 에너지는 높은 편이었어요."
        )
    else:
        summary.append(
            "기록된 평균 에너지는 중간 수준이었어요."
        )

    if len(points) >= 2:
        valences = [
            point.mainValence
            for point in points
        ]

        if max(valences) - min(valences) >= 2:
            summary.append(
                "기록 시점에 따라 감정 방향에 차이가 있었어요."
            )
            questions.append(
                "감정이 달라졌던 시점에 어떤 일이 있었나요?"
            )

    if not questions:
        if negative_count > 0 and avg_energy <= 2:
            questions.append(
                "오늘 나에게 가장 필요한 휴식이나 도움은 무엇인가요?"
            )
        elif positive_ratio >= 0.65:
            questions.append(
                "오늘 기분에 도움이 되었던 순간은 무엇이었나요?"
            )
        else:
            questions.append(
                "오늘 가장 기억에 남는 순간과 감정은 무엇인가요?"
            )

    return {
        "summary": summary,
        "reflection_questions": questions,
    }
