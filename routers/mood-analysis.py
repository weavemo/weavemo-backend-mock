# routers/mood_analysis.py (Week 9 — Reflection Analysis API)

from fastapi import APIRouter, Depends
from dependencies.auth import get_current_user
from db.database import get_supabase
from services.mood_analysis_service import build_reflection_analysis

router = APIRouter()

@router.get("/mood-analysis/today")
def get_today_reflection_analysis(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    # 이미 계산된 metrics 조회 (기존 로직 재사용)
    metrics = supabase.rpc("get_today_mood_metrics", {"uid": user_id}).execute()

    if not metrics.data:
        return {
            "summary": ["오늘은 기록된 감정 데이터가 충분하지 않습니다."],
            "reflection_questions": [],
        }

    # metrics → 문장 변환 (Week 9 핵심)
    analysis = build_reflection_analysis(metrics.data)

    return analysis
