#weavemo-backend-mock/routers/weekly_summaries.py

from fastapi import APIRouter, Depends, Query

from dependencies.auth import get_current_user
from db.database import get_supabase

router = APIRouter()


@router.get("/weekly-summaries")
def get_weekly_summary(
    week_start: str = Query(...),
    current_user=Depends(get_current_user),
):
    """
    Frontend contract:
    GET /weekly-summaries?week_start=YYYY-MM-DD
    returns a single WeeklySummary object.
    """
    supabase = get_supabase()
    user_id = current_user["user_id"]

    res = (
        supabase.table("weekly_summaries")
        .select("*")
        .eq("user_id", user_id)
        .eq("week_start", week_start)
        .limit(1)
        .execute()
    )

    rows = res.data or []
    if rows:
        return rows[0]

    # 데이터 없으면 프론트에서 "데이터 없음" 처리하도록 null-ish 응답
    return {
        "week_start": week_start,
        "avg_valence": None,
        "avg_energy": None,
        "top_emotions": None,
        "weekday_pattern": None,
        "summary_text": None,
        "created_at": None,
    }
