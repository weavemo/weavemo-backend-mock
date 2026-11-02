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

# file: weavemo-backend-mock/routers/action.py

# routers/action.py

@router.post("/complete")
def complete_action(
    body: dict,
    current_user=Depends(get_current_user),
):
    action_id = body.get("action_id")

    if (
        type(action_id) is not int
        or not 0 < action_id <= 9223372036854775807
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid action ID",
        )

    supabase = get_supabase()

    params = {
        "p_user_id": current_user["user_id"],
        "p_auth_uid": current_user["auth_uid"],
        "p_action_id": action_id,
    }

    # 전환 중인 기존 화면은 기존 완료 방식을 유지한다.
    if "tz_offset_min" not in body:
        result = supabase.rpc(
            "complete_action_with_fragment",
            params,
        ).execute()

        return result.data

    tz_offset_min = body["tz_offset_min"]

    if (
        type(tz_offset_min) is not int
        or not -840 <= tz_offset_min <= 840
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid timezone offset",
        )

    # 새 화면은 행동 완료와 XP 지급을 한 번에 처리한다.
    params["p_tz_offset_min"] = tz_offset_min

    # 저장 요청은 자동 재시도하지 않는다.
    result = supabase.rpc(
        "complete_action_with_rewards",
        params,
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
