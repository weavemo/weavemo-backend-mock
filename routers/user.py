# routers/user.py
from fastapi import APIRouter, Depends
from dependencies.auth import get_current_user

router = APIRouter()


@router.get("/me")
def get_my_profile(current_user=Depends(get_current_user)):
    return {
        "user": current_user
    }

@router.patch("/frame")
def update_frame(
    frame: str,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    supabase.table("user_stats").update({
        "equipped_frame": frame
    }).eq("user_id", user_id).execute()

    return {"equipped_frame": frame}
