# routers/journal_entries.py

from fastapi import APIRouter, Depends, Query, Body, Header
from datetime import date, datetime
from dependencies.auth import get_current_user
from db.database import get_supabase

router = APIRouter()


@router.post("")
def create_journal_entry(
    content: str = Body(None),
    date: date = Body(None),
    type: str = Body(None),
    tz_offset_min: int = Header(0),
    current_user=Depends(get_current_user),
):
    if content is None or date is None or type is None:
        raise ValueError("content, date, type required")

    supabase = get_supabase()
    user_id = current_user["user_id"]

    supabase.table("journal_entries").insert({
        "user_id": user_id,
        "content": content,
        "date": date.isoformat(),
        "type": type,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    return {"ok": True}


@router.post("/reflection")
def create_reflection(
    content: str = Body(None),
    week_start: date = Body(None),
    current_user=Depends(get_current_user),
):
    if content is None or week_start is None:
        raise ValueError("content, week_start required")

    supabase = get_supabase()
    user_id = current_user["user_id"]

    exists = (
        supabase.table("journal_entries")
        .select("id")
        .eq("user_id", user_id)
        .eq("type", "reflection")
        .eq("date", week_start.isoformat())
        .limit(1)
        .execute()
    )

    if exists.data:
        return {"ok": False, "error": "reflection_already_exists"}

    supabase.table("journal_entries").insert({
        "user_id": user_id,
        "content": content,
        "date": week_start.isoformat(),
        "type": "reflection",
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    return {"ok": True}


@router.get("/reflection")
def get_reflection(
    week_start: date = Query(None),
    current_user=Depends(get_current_user),
):
    if week_start is None:
        raise ValueError("week_start required")

    supabase = get_supabase()
    user_id = current_user["user_id"]

    res = (
        supabase.table("journal_entries")
        .select("content, date, created_at")
        .eq("user_id", user_id)
        .eq("type", "reflection")
        .eq("date", week_start.isoformat())
        .limit(1)
        .execute()
    )

    if not res.data:
        return {"item": None}

    return {"item": res.data[0]}


@router.get("/reflection_weeks")
def get_reflection_weeks(
    month: str = Query(None),
    current_user=Depends(get_current_user),
):
    if month is None:
        raise ValueError("month required")

    supabase = get_supabase()
    user_id = current_user["user_id"]

    year, mon = map(int, month.split("-"))
    start = date(year, mon, 1)

    if mon == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, mon + 1, 1)

    res = (
        supabase.table("journal_entries")
        .select("date")
        .eq("user_id", user_id)
        .eq("type", "reflection")
        .gte("date", start.isoformat())
        .lt("date", end.isoformat())
        .execute()
    )

    weeks = sorted({row["date"] for row in res.data})
    return {"weeks": weeks}


@router.get("/by-date")
def get_by_date(
    date: date = Query(None),
    current_user=Depends(get_current_user),
):
    if date is None:
        raise ValueError("date required")

    supabase = get_supabase()
    user_id = current_user["user_id"]

    res = (
        supabase.table("journal_entries")
        .select("*")
        .eq("user_id", user_id)
        .eq("date", date.isoformat())
        .order("created_at", desc=False)
        .execute()
    )

    return {"items": res.data}


@router.get("/dates")
def get_entry_dates(
    month: str = Query(None),
    current_user=Depends(get_current_user),
):
    if month is None:
        raise ValueError("month required")

    supabase = get_supabase()
    user_id = current_user["user_id"]

    start = f"{month}-01"
    year, mon = map(int, month.split("-"))

    if mon == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{mon + 1:02d}-01"

    res = (
        supabase.table("journal_entries")
        .select("date")
        .eq("user_id", user_id)
        .gte("date", start)
        .lt("date", end)
        .execute()
    )

    dates = sorted({row["date"] for row in res.data})
    return {"dates": dates}
