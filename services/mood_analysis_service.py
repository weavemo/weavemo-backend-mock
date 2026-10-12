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
        1 for point in points if point.mainValence > 0
    )
    negative_count = sum(
        1 for point in points if point.mainValence < 0
    )

    positive_ratio = positive_count / len(points)
    negative_ratio = negative_count / len(points)
    avg_energy = analysis.metrics.avg_energy

    if positive_ratio >= 0.65:
        summary.append("reflection_summary.POSITIVE")
    elif negative_ratio >= 0.65:
        summary.append("reflection_summary.NEGATIVE")
    elif positive_count > 0 and negative_count > 0:
        summary.append("reflection_summary.MIXED")
    else:
        summary.append("reflection_summary.NEUTRAL")

    if avg_energy <= 2:
        summary.append("reflection_summary.LOW_ENERGY")
    elif avg_energy >= 4:
        summary.append("reflection_summary.HIGH_ENERGY")
    else:
        summary.append("reflection_summary.MID_ENERGY")

    if len(points) >= 2:
        valences = [point.mainValence for point in points]

        if max(valences) - min(valences) >= 2:
            summary.append("reflection_summary.VARIATION")
            questions.append("reflection_questions.CHANGE")

    if not questions:
        if negative_count > 0 and avg_energy <= 2:
            questions.append("reflection_questions.RECOVERY")
        elif positive_ratio >= 0.65:
            questions.append("reflection_questions.POSITIVE")
        else:
            questions.append("reflection_questions.MEMORABLE")

    return {
        "summary": summary,
        "reflection_questions": questions,
    }
