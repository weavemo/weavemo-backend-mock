from fastapi import APIRouter, Depends, Body
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
    action_id: int = Body(...),
    current_user=Depends(get_current_user),
):
    try:
        supabase = get_supabase()

        user_id = current_user["user_id"]

        # 중복 방지
        existing = (
            supabase.table("user_actions")
            .select("id")
            .eq("user_id", user_id)
            .eq("action_id", action_id)
            .execute()
        )

        if existing.data:
            return {"ok": True}

        # 완료 기록
        supabase.table("user_actions").insert({
            "user_id": user_id,
            "action_id": action_id
        }).execute()

        # XP 조회
        user = (
            supabase.table("users")
            .select("xp")
            .eq("id", user_id)
            .single()
            .execute()
        )

        current_xp = user.data.get("xp", 0)
        new_xp = current_xp + 10

        # XP 업데이트
        supabase.table("users").update({
            "xp": new_xp
        }).eq("id", user_id).execute()

        return {"ok": True, "xp": new_xp}

    except Exception:
        traceback.print_exc()
        raise
