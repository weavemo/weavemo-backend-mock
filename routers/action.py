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
            .select("id, title, description, type")
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
    try:
        supabase = get_supabase()

        action_id = body.get("action_id")
        user_id = current_user["user_id"]

        res = (
            supabase.table("user_actions")
            .insert({
                "user_id": user_id,
                "action_id": action_id,
            })
            .execute()
        )

        return {"success": True}

    except Exception:
        traceback.print_exc()
        raise
