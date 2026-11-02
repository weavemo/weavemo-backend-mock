#routers/action.py

from fastapi import APIRouter, Depends, HTTPException
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
    action_id = body.get("action_id")
    tz_offset_min = body.get("tz_offset_min")

    if (
        type(action_id) is not int
        or not 0 < action_id <= 9223372036854775807
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid action ID",
        )

    # 시간대가 빠진 요청을 임의로 UTC 기준으로 처리하지 않는다.
    if (
        type(tz_offset_min) is not int
        or not -840 <= tz_offset_min <= 840
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid timezone offset",
        )

    # 행동 기록과 보상·XP 지급을 하나의 트랜잭션으로 처리한다.
    # 저장 요청은 자동 재시도하지 않는다.
    result = get_supabase().rpc(
        "complete_action_with_rewards",
        {
            "p_user_id": current_user["user_id"],
            "p_auth_uid": current_user["auth_uid"],
            "p_action_id": action_id,
            "p_tz_offset_min": tz_offset_min,
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
