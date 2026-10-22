# weavemo-backend-mock/routers/onboarding.py

from fastapi import APIRouter, Depends, HTTPException

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()


@router.get("/onboarding")
def get_onboarding_status(
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()

    result = (
        supabase.table("users")
        .select("onboarding_completed")
        .eq("id", current_user["user_id"])
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return {
        "completed": result.data[0]["onboarding_completed"],
    }


@router.put("/onboarding/complete")
def complete_onboarding(
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()

    # 여러 번 요청해도 완료 상태는 동일하다.
    result = (
        supabase.table("users")
        .update({"onboarding_completed": True})
        .eq("id", current_user["user_id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return {"completed": True}
