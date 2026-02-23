#weavemo-backend-mock/routers/weekly_summaries.py

from fastapi import APIRouter, Depends, Query

from dependencies.auth import get_current_user
from db.database import get_supabase
from services.weekly_summary_service import build_weekly_summary

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

    # 없으면 즉시 집계해서 생성 (Week 9: 최소 수정 자동 집계)
    payload = build_weekly_summary(
        supabase=supabase,
        user_id=user_id,
        week_start=week_start,
    )

    # upsert by (user_id, week_start) — unique constraint가 없다면 insert로만 동작
    supabase.table("weekly_summaries").upsert(payload, on_conflict="user_id,week_start").execute()

    # 다시 조회해서 DB의 created_at 포함해서 반환
    res2 = (
        supabase.table("weekly_summaries")
        .select("*")
        .eq("user_id", user_id)
        .eq("week_start", week_start)
        .limit(1)
        .execute()
    )
    return (res2.data or [payload])[0]
