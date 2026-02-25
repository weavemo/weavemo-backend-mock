#weavemo-backend-mock/routers/weekly_summaries.py

from fastapi import APIRouter, Depends, Query

from dependencies.auth import get_current_user
from db.database import get_supabase
from services.weekly_summary_service import build_weekly_summary
from postgrest.exceptions import APIError

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
        row = rows[0]
        # ✅ "빈 리포트"면 재계산해서 채우기 (최소 수정)
        is_empty = (
            row.get("weekday_pattern") is None
            and row.get("summary_text") is None
            and (row.get("mood_checks") in [None, 0])
        )
        if not is_empty:
            return row
        payload = build_weekly_summary(
            supabase=supabase,
            user_id=user_id,
            week_start=week_start,
        )
        # ✅ unique constraint 없어도 안전하게: id로 update
        supabase.table("weekly_summaries").upsert(payload, on_conflict="user_id,week_start").execute()
        res2 = supabase.table("weekly_summaries").select("*").eq("id", row["id"]).limit(1).execute()
        return (res2.data or [payload])[0]

    # 없으면 즉시 집계해서 생성 (Week 9: 최소 수정 자동 집계)
    payload = build_weekly_summary(
        supabase=supabase,
        user_id=user_id,
        week_start=week_start,
    )

    # upsert by (user_id, week_start) — unique constraint가 없다면 insert로만 동작
    # ✅ 없으면 생성 (중복이면 upsert로 흡수)
    try:
        supabase.table("weekly_summaries").upsert(payload, on_conflict="user_id,week_start").execute()
    except APIError as e:
        # 혹시나 race condition 등으로 23505가 나도, 다시 select 해서 반환
        if getattr(e, "args", None) and isinstance(e.args[0], dict) and e.args[0].get("code") == "23505":
            pass
        else:
            raise
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
