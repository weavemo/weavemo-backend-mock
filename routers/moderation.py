# weavemo-backend-mock/routers/moderation.py

import logging

from fastapi import APIRouter, Depends, HTTPException

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_BIGINT = 9223372036854775807


def valid_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and len(value) <= 19
        and 0 < int(value) <= MAX_BIGINT
    )


@router.get("/me")
def get_my_moderation_status(
    current_user=Depends(get_current_user),
):
    try:
        result = get_supabase().rpc(
            "weavemo_my_moderation_status",
            {
                # 他人のIDは受け取らず、認証済み本人だけを 조회한다.
                "p_actor": int(current_user["user_id"]),
            },
        ).execute()
    except Exception as error:
        logger.exception("My moderation status lookup failed")

        raise HTTPException(
            status_code=503,
            detail="Could not load moderation status",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid moderation status response",
        )

    restricted = data.get("messaging_restricted")
    restricted_until = data.get("restricted_until")
    restrictions = data.get("restrictions")
    warnings = data.get("warnings")

    valid = (
        isinstance(restricted, bool)
        and isinstance(restrictions, list)
        and isinstance(warnings, list)
        and (
            restricted_until is None
            or isinstance(restricted_until, str)
        )
    )

    if not valid:
        raise HTTPException(
            status_code=503,
            detail="Invalid moderation status response",
        )

    if restricted != bool(restrictions) or (
        restricted != (restricted_until is not None)
    ):
        raise HTTPException(
            status_code=503,
            detail="Inconsistent moderation status response",
        )

    public_restrictions = []
    public_warnings = []

    for item in restrictions:
        if (
            not isinstance(item, dict)
            or not valid_id(item.get("id"))
            or not isinstance(item.get("reason"), str)
            or not isinstance(item.get("created_at"), str)
            or not isinstance(item.get("expires_at"), str)
        ):
            raise HTTPException(
                status_code=503,
                detail="Invalid restriction response",
            )

        public_restrictions.append({
            "id": item["id"],
            "reason": item["reason"],
            "created_at": item["created_at"],
            "expires_at": item["expires_at"],
        })

    for item in warnings:
        if (
            not isinstance(item, dict)
            or not valid_id(item.get("id"))
            or not isinstance(item.get("reason"), str)
            or not isinstance(item.get("created_at"), str)
        ):
            raise HTTPException(
                status_code=503,
                detail="Invalid warning response",
            )

        public_warnings.append({
            "id": item["id"],
            "reason": item["reason"],
            "created_at": item["created_at"],
        })

    return {
        "messaging_restricted": restricted,
        "restricted_until": restricted_until,
        "restrictions": public_restrictions,
        "warnings": public_warnings,
    }
