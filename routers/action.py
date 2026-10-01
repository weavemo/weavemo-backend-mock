#routers/action.py

from fastapi import APIRouter, Depends
from db.database import get_supabase
from dependencies.auth import get_current_user
import traceback

router = APIRouter()

@router.get("/recommended")
def get_recommended_actions(current_user=Depends(get_current_user)):
    try:
        print("current_user =", current_user)

        supabase = get_supabase()
        print("supabase client ok")

        res = (
            supabase.table("actions")
            .select(
                "id, title, description, type, "
                "duration_sec, difficulty, "
                "is_premium, recommended_for"
            )
            .eq("is_active", True)
            .execute()
        )

        print("recommended res =", res.data)

        return {
            "actions": res.data or []
        }
    except Exception:
        traceback.print_exc()
        raise

# file: weavemo-backend-mock/routers/action.py

@router.post("/complete")
def complete_action(
    body: dict,
    current_user=Depends(get_current_user),
):
    action_id = body.get("action_id")

    if isinstance(action_id, bool):
        action_id = None

    try:
        action_id = int(action_id)
    except (TypeError, ValueError):
        action_id = None

    if action_id is None or action_id <= 0:
        return {
            "ok": False,
            "error": "invalid_action_id",
        }

    supabase = get_supabase()

    result = supabase.rpc(
        "complete_action_with_fragment",
        {
            "p_user_id": current_user["user_id"],
            "p_auth_uid": current_user["auth_uid"],
            "p_action_id": action_id,
        },
    ).execute()

    return result.data

@router.get("/completed/count")
def get_completed_action_count(
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    res = (
        supabase.table("action_logs")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )

    return {
        "count": res.count or 0
    }
