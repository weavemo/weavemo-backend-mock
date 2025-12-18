from fastapi import APIRouter, Depends
from datetime import datetime
from dependencies.auth import get_current_user
from db.database import get_supabase

router = APIRouter()


@router.post("/check")
def check_badges(
    source: str,  # action | journal | mood
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    # user_stats 조회
    stats_res = (
        supabase.table("user_stats")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    stats = stats_res.data[0]

    earned = []

    # --- RULES (Week5 최소셋) ---

    # 1️⃣ 행동 5회
    if source == "action" and stats["total_actions"] >= 5:
        earned.append("calmdown_rookie")

    # 2️⃣ 일기 5회
    if source == "journal" and stats["total_journals"] >= 5:
        earned.append("journal_starter")

    # 3️⃣ 스트릭 7일
    if stats["streak_days"] >= 7:
        earned.append("streak_7")

    if not earned:
        return {"earned": []}

    # badge master 조회
    badges = (
        supabase.table("badges")
        .select("id, code")
        .in_("code", earned)
        .execute()
        .data
    )

    # 이미 받은 뱃지 제거
    owned = (
        supabase.table("user_badges")
        .select("badge_id")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    owned_ids = {o["badge_id"] for o in owned}

    new_badges = [b for b in badges if b["id"] not in owned_ids]

    for b in new_badges:
        supabase.table("user_badges").insert({
            "user_id": user_id,
            "badge_id": b["id"],
            "earned_at": datetime.utcnow().isoformat(),
        }).execute()

    return {
        "earned": [b["code"] for b in new_badges]
    }
