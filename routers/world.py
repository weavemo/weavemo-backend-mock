# routers/world.py

import logging

from fastapi import APIRouter, Depends, HTTPException

from db.database import get_supabase
from dependencies.auth import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/initialize")
def initialize_world(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    user_id = current_user["user_id"]

    try:
        # 요청 본문에서 사용자 ID를 받지 않는다.
        # 기존 World와 동물이 있으면 현재 상태를 반환한다.
        result = supabase.rpc(
            "initialize_my_world",
            {
                "p_user_id": user_id,
            },
        ).execute()
    except Exception as error:
        logger.exception("World initialization failed")

        raise HTTPException(
            status_code=503,
            detail="Could not initialize world",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid world response",
        )

    world = data.get("world")
    companion = data.get("companion")

    if (
        not isinstance(world, dict)
        or not isinstance(companion, dict)
        or str(world.get("user_id")) != str(user_id)
        or str(companion.get("user_id")) != str(user_id)
        or not isinstance(world.get("terrain_key"), str)
        or world.get("visibility") not in (
            "private",
            "friends",
            "public",
        )
        or companion.get("stage") not in (
            "egg",
            "hatched",
            "grown",
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid world response",
        )

    return data
