# weavemo-backend-mock/routers/friends.py

from fastapi import APIRouter, Depends, HTTPException, Query

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()


@router.get("/search")
def search_users(
    q: str = Query(..., min_length=2, max_length=30),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]
    keyword = q.strip()

    if len(keyword) < 2:
        raise HTTPException(
            status_code=400,
            detail="Enter at least two characters",
        )

    # LIKE 검색에서 특수문자를 일반 문자로 처리한다.
    escaped_keyword = (
        keyword.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )

    result = (
        supabase.table("users")
        .select("id, nickname, profile_image_url")
        .neq("id", user_id)
        .ilike("nickname", f"%{escaped_keyword}%")
        .order("nickname")
        .order("id")
        .limit(20)
        .execute()
    )

    candidates = result.data or []

    if not candidates:
        return {"items": []}

    candidate_ids = [user["id"] for user in candidates]

    outgoing_blocks = (
        supabase.table("user_blocks")
        .select("blocked_id")
        .eq("blocker_id", user_id)
        .in_("blocked_id", candidate_ids)
        .execute()
    )

    incoming_blocks = (
        supabase.table("user_blocks")
        .select("blocker_id")
        .eq("blocked_id", user_id)
        .in_("blocker_id", candidate_ids)
        .execute()
    )

    excluded_ids = {
        row["blocked_id"]
        for row in outgoing_blocks.data or []
    }
    excluded_ids.update(
        row["blocker_id"]
        for row in incoming_blocks.data or []
    )

    return {
        "items": [
            {
                # bigint ID는 프런트에서 문자열로 취급한다.
                "id": str(user["id"]),
                "nickname": user.get("nickname") or "",
                "profile_image_url": user.get("profile_image_url"),
            }
            for user in candidates
            if user["id"] not in excluded_ids
        ]
    }
