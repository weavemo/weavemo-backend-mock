from fastapi import APIRouter, Depends
from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()

@router.get("/recommended")
def get_recommended_actions(current_user=Depends(get_current_user)):
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
