# services/mood_analysis_service.py (Week 9 — 문장 생성 레이어)

from typing import Dict, List


def build_reflection_analysis(metrics: Dict) -> Dict:
    summary: List[str] = []
    questions: List[str] = []

    positive = metrics.get("positive_ratio")
    entropy = metrics.get("emotion_entropy")
    energy = metrics.get("energy_score")

    # --- Summary sentence ① ---
    if positive >= 0.65:
        summary.append("오늘은 전반적으로 안정적인 정서 흐름이 이어진 하루였습니다.")
    elif positive >= 0.36:
        summary.append("오늘은 긍정과 부정 감정이 섞여 나타난 복합적인 하루였습니다.")
    else:
        summary.append("오늘은 정서적으로 부담이 누적된 흐름이 감지된 하루였습니다.")

    # --- Summary sentence ② ---
    if entropy >= 0.6:
        summary.append("상황에 따라 감정이 자주 전환되는 패턴이 관찰되었습니다.")
    else:
        summary.append("감정의 큰 변동 없이 하루가 비교적 일정하게 진행되었습니다.")

    # --- Reflection Questions ---
    if positive < 0.36 and energy < 0.4:
        questions.append("지금 상태에서 가장 먼저 회복이 필요한 부분은 무엇인가요?")
    elif entropy >= 0.6:
        questions.append("감정이 바뀌는 전환점이 되었던 순간은 언제였나요?")
    else:
        questions.append("이런 하루의 흐름을 만든 요인은 무엇이었을까요?")

    return {
        "summary": summary,
        "reflection_questions": questions,
    }
