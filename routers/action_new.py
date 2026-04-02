from fastapi import APIRouter, Depends, Body
from db.database import get_supabase
from dependencies.auth import get_current_user
import traceback

router = APIRouter()


@router.get("/recommended")
def get_recommended_actions(current_user=Depends(get_current_user)):
    try:
        supabase = get_supabase()

        res = (
            supabase.table("actions")
            .select("id, title, description, type")
            .eq("is_active", True)
            .execute()
        )

        return {
            "actions": res.data or []
        }
    except Exception:
        traceback.print_exc()
        return {"actions": []}  # 🔥 죽지 않게


@router.post("/complete")
def complete_action(
    action_id: int = Body(...),
    current_user=Depends(get_current_user),
):
    try:
        supabase = get_supabase()
        user_id = current_user["user_id"]

        # 🔥 1️⃣ 중복 체크 + insert 최소화
        existing = (
            supabase.table("user_actions")
            .select("id")
            .eq("user_id", user_id)
            .eq("action_id", action_id)
            .limit(1)
            .execute()
        )

        if not existing.data:
            supabase.table("user_actions").insert({
                "user_id": user_id,
                "action_id": action_id
            }).execute()

        # 🔥 2️⃣ XP 조회 제거 (fallback 포함)
        try:
            user = (
                supabase.table("users")
                .select("xp")
                .eq("id", user_id)
                .single()
                .execute()
            )
            current_xp = user.data.get("xp", 0)
        except Exception:
            current_xp = 0  # 🔥 fallback

        new_xp = current_xp + 10

        # 🔥 3️⃣ update 실패해도 죽지 않게
        try:
            supabase.table("users").update({
                "xp": new_xp
            }).eq("id", user_id).execute()
        except Exception:
            pass

        return {"ok": True, "xp": new_xp}

    except Exception:
        traceback.print_exc()
        return {"ok": False, "xp": 0}  # 🔥 절대 raise 하지 마
