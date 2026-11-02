# routers/community_reports.py

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from postgrest.exceptions import APIError
from pydantic import BaseModel, ConfigDict, Field

from db.database import get_supabase
from dependencies.auth import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)

MAX_BIGINT = 9223372036854775807


class CommunityReportRequest(BaseModel):
    # 신고자 ID나 신고 당시 내용은 클라이언트에서 받지 않는다.
    model_config = ConfigDict(extra="forbid")

    reason: Literal[
        "spam",
        "harassment",
        "sexual_content",
        "threat",
        "other",
    ]
    details: str = Field(default="", max_length=1000)


def submit_community_report(
    supabase,
    current_user: dict,
    post_id: int,
    comment_id: int | None,
    body: CommunityReportRequest,
) -> dict:
    try:
        # 저장 요청은 자동 재시도하지 않는다.
        result = supabase.rpc(
            "weavemo_report_community",
            {
                "p_actor": int(current_user["user_id"]),
                "p_post_id": post_id,
                "p_comment_id": comment_id,
                "p_reason": body.reason,
                "p_details": body.details,
            },
        ).execute()

    except APIError as error:
        # 직접 발생시킨 DB 예외만 정해진 HTTP 오류로 변환한다.
        known_errors = {
            "invalid_request": (400, "Invalid report request"),
            "not_found": (404, "Content not found"),
            "self_report_not_allowed": (
                403,
                "Cannot report your own content",
            ),
        }

        mapped = (
            known_errors.get(error.message)
            if error.code == "P0001"
            else None
        )

        if mapped:
            status_code, detail = mapped
            raise HTTPException(
                status_code=status_code,
                detail=detail,
            ) from error

        logger.exception("Community report database request failed")
        raise HTTPException(
            status_code=503,
            detail="Could not submit report",
        ) from error

    except Exception as error:
        logger.exception("Community report request failed")
        raise HTTPException(
            status_code=503,
            detail="Could not submit report",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid report response",
        )

    report_id = data.get("report_id")
    created = data.get("created")

    valid_id = (
        isinstance(report_id, str)
        and report_id.isascii()
        and report_id.isdecimal()
        and len(report_id) <= 19
        and 0 < int(report_id) <= MAX_BIGINT
    )

    if not valid_id or not isinstance(created, bool):
        raise HTTPException(
            status_code=503,
            detail="Invalid report response",
        )

    # 작성자 ID나 신고 당시 내용은 신고자에게 반환하지 않는다.
    return {
        "report_id": report_id,
        "created": created,
    }


@router.post("/{post_id}/report")
def report_post(
    body: CommunityReportRequest,
    post_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    return submit_community_report(
        supabase=supabase,
        current_user=current_user,
        post_id=post_id,
        comment_id=None,
        body=body,
    )


@router.post("/{post_id}/comments/{comment_id}/report")
def report_comment(
    body: CommunityReportRequest,
    post_id: int = Path(..., ge=1, le=MAX_BIGINT),
    comment_id: int = Path(..., ge=1, le=MAX_BIGINT),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    return submit_community_report(
        supabase=supabase,
        current_user=current_user,
        post_id=post_id,
        comment_id=comment_id,
        body=body,
    )
