# weavemo-backend-mock/dependencies/admin.py

import logging

from fastapi import Depends, HTTPException

from db.database import get_supabase
from dependencies.auth import get_current_user

logger = logging.getLogger(__name__)


def require_admin(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        result = (
            supabase.table("app_admins")
            .select("user_id")
            .eq("user_id", current_user["user_id"])
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.exception("Admin permission lookup failed")

        raise HTTPException(
            status_code=503,
            detail="Admin permission check unavailable",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    return current_user
