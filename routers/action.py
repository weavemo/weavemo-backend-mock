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

@router.post("/complete")
def complete_action(
    body: dict,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    action_id = body.get("action_id")

    if action_id is None:
        return {
            "ok": False,
            "error": "action_id_required",
        }

    supabase.table("action_logs").insert({
        "user_id": user_id,
        "action_id": action_id,
    }).execute()

    return {
        "ok": True,
    }

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
