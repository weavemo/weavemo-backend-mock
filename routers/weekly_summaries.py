from fastapi import APIRouter, Depends, Query

from dependencies.auth import get_current_user
from db.database import get_supabase
from services.weekly_summary_service import build_weekly_summary
from postgrest.exceptions import APIError

router = APIRouter()


def _visible_weekly_summary(row: dict, is_premium: bool) -> dict:
    if is_premium:
        return row

    # Whitelist basic fields so newly added premium fields are not exposed.
    basic_fields = (
        "week_start", "week_end", "avg_valence", "avg_energy",
        "mood_checks", "journal_days", "points_gained", "points_possible",
    )
    result = {key: row[key] for key in basic_fields if key in row}
    pattern = row.get("weekday_pattern")
    if isinstance(pattern, list):
        result["weekday_pattern"] = [
            {key: item[key] for key in ("day", "valence", "energy") if key in item}
            for item in pattern if isinstance(item, dict)
        ]
    else:
        result["weekday_pattern"] = None
    emotions = row.get("top_emotions")
    result["top_emotions"] = [
        {key: item[key] for key in ("code", "count") if key in item}
        for item in emotions if isinstance(item, dict)
    ] if isinstance(emotions, list) else []
    return result


@router.get("/weekly-summaries")
def get_weekly_summary(
    week_start: str = Query(None),
    current_user=Depends(get_current_user),
):
    if week_start is None:
        raise ValueError("Week_start is required")
    supabase = get_supabase()
    user_id = current_user["user_id"]
    is_premium = current_user.get("plan") == "premium"

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
        is_empty = (
            row.get("weekday_pattern") is None
            and row.get("summary_text") is None
            and (row.get("mood_checks") in [None, 0])
        )
        if not is_empty:
            return _visible_weekly_summary(row, is_premium)
        payload = build_weekly_summary(
            supabase=supabase,
            user_id=user_id,
            week_start=week_start,
        )
        supabase.table("weekly_summaries").upsert(payload, on_conflict="user_id,week_start").execute()
        res2 = supabase.table("weekly_summaries").select("*").eq("id", row["id"]).limit(1).execute()
        return _visible_weekly_summary((res2.data or [payload])[0], is_premium)

    payload = build_weekly_summary(
        supabase=supabase,
        user_id=user_id,
        week_start=week_start,
    )

    try:
        supabase.table("weekly_summaries").upsert(payload, on_conflict="user_id,week_start").execute()
    except APIError as e:
        if getattr(e, "args", None) and isinstance(e.args[0], dict) and e.args[0].get("code") == "23505":
            pass
        else:
            raise
    res2 = (
        supabase.table("weekly_summaries")
        .select("*")
        .eq("user_id", user_id)
        .eq("week_start", week_start)
        .limit(1)
        .execute()
    )
    return _visible_weekly_summary((res2.data or [payload])[0], is_premium)
