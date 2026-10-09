# routers/badge.py

from fastapi import APIRouter, Depends
from dependencies.auth import get_current_user
from db.database import get_supabase
from routers.mood import get_unique_mood_count
router = APIRouter()


@router.get("")
def get_my_badges(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    res = (
        supabase.table("user_badges")
        .select("badge_id, earned_at, badges(id, code, name)")
        .eq("user_id", user_id)
        .execute()
    )

    items = []

    for row in res.data or []:
        badge = row.get("badges")
        if not badge:
            continue

        items.append({
            "id": str(badge["id"]),
            "code": badge["code"],
            "name": badge["name"],
            "unlocked": True,
        })

    return items


@router.post("/check")
def check_badges(
    source: str | None = None,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    stats_res = (
        supabase.table("user_stats")
        .select(
            "streak_days, total_moods, "
            "total_journals, total_actions"
        )
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not stats_res.data:
        return {"earned": []}

    stats = stats_res.data[0]

    badges_res = (
        supabase.table("badges")
        .select("id, code, condition_type, condition_value")
        .execute()
    )

    owned_res = (
        supabase.table("user_badges")
        .select("badge_id")
        .eq("user_id", user_id)
        .execute()
    )

    owned_ids = {
        row["badge_id"]
        for row in owned_res.data or []
    }

    earned = []

    for badge in badges_res.data or []:
        if badge["id"] in owned_ids:
            continue

        condition = badge["condition_type"]
        required = badge["condition_value"]

        if badge["code"] == "all_moods":
            # 기존 API와 동일한 8개 감정 태그를 집계한다.
            mood_count = get_unique_mood_count(
                supabase=supabase,
                current_user=current_user,
            )

            if mood_count["count"] < 8:
                continue
        else:
            if condition not in {
                "streak_days",
                "total_moods",
                "total_journals",
                "total_actions",
            }:
                continue

            actual = stats.get(condition) or 0

            if actual < required:
                continue
        supabase.table("user_badges").insert({
            "user_id": user_id,
            "badge_id": badge["id"],
        }).execute()

        earned.append(badge["code"])
        owned_ids.add(badge["id"])

    return {"earned": earned}
