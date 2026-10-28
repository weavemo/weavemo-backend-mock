# weavemo-backend-mock/routers/admin_notes.py

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from db.database import get_supabase
from dependencies.admin import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_BIGINT = 9223372036854775807

REPORT_COLUMNS = (
    "id, note_id, reporter_id, reported_user_id, "
    "reason, details, status, created_at, reviewed_at"
)


class ReportStatusRequest(BaseModel):
    status: Literal["reviewed", "dismissed"]


def public_report(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "note_id": str(row["note_id"]),
        "reporter_id": str(row["reporter_id"]),
        "reported_user_id": str(row["reported_user_id"]),
        "reason": row["reason"],
        "details": row["details"],
        "status": row["status"],
        "created_at": row["created_at"],
        "reviewed_at": row.get("reviewed_at"),
    }


@router.get("/access")
def get_admin_access(
    admin=Depends(require_admin),
):
    return {"admin": True}


@router.get("/note-reports")
def list_note_reports(
    status: Literal[
        "pending", "reviewed", "dismissed", "all"
    ] = "pending",
    before_id: int | None = Query(
        None, ge=1, le=MAX_BIGINT
    ),
    limit: int = Query(20, ge=1, le=50),
    admin=Depends(require_admin),
):
    try:
        query = (
            get_supabase()
            .table("note_reports")
            .select(REPORT_COLUMNS)
        )

        if status != "all":
            query = query.eq("status", status)

        if before_id is not None:
            query = query.lt("id", before_id)

        result = (
            query.order("id", desc=True)
            .limit(limit + 1)
            .execute()
        )
    except Exception as error:
        logger.exception("Admin report list failed")

        raise HTTPException(
            status_code=503,
            detail="Could not load reports",
        ) from error

    rows = result.data or []
    page = rows[:limit]

    return {
        "items": [public_report(row) for row in page],
        "next_cursor": (
            str(page[-1]["id"])
            if len(rows) > limit and page
            else None
        ),
    }


@router.get("/note-reports/{report_id}")
def get_note_report(
    report_id: int = Path(..., ge=1, le=MAX_BIGINT),
    admin=Depends(require_admin),
):
    supabase = get_supabase()

    try:
        result = (
            supabase.table("note_reports")
            .select(REPORT_COLUMNS)
            .eq("id", report_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Report not found",
            )

        report = result.data[0]

        note_result = (
            supabase.table("friend_notes")
            .select("id, body, created_at")
            .eq("id", report["note_id"])
            .limit(1)
            .execute()
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Admin report detail failed")

        raise HTTPException(
            status_code=503,
            detail="Could not load report",
        ) from error

    note = note_result.data[0] if note_result.data else None

    return {
        "report": public_report(report),
        "note": (
            {
                "id": str(note["id"]),
                "body": note["body"],
                "created_at": note["created_at"],
            }
            if note
            else None
        ),
    }


@router.patch("/note-reports/{report_id}")
def update_note_report(
    body: ReportStatusRequest,
    report_id: int = Path(..., ge=1, le=MAX_BIGINT),
    admin=Depends(require_admin),
):
    supabase = get_supabase()

    try:
        # 대기 중인 신고만 처리한다.
        # 동시에 다른 운영자가 처리했다면 덮어쓰지 않는다.
        result = (
            supabase.table("note_reports")
            .update({
                "status": body.status,
                "reviewed_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            })
            .eq("id", report_id)
            .eq("status", "pending")
            .execute()
        )

        if result.data:
            return public_report(result.data[0])

        existing = (
            supabase.table("note_reports")
            .select(REPORT_COLUMNS)
            .eq("id", report_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.exception("Admin report update failed")

        raise HTTPException(
            status_code=503,
            detail="Could not update report",
        ) from error

    if not existing.data:
        raise HTTPException(
            status_code=404,
            detail="Report not found",
        )

    report = existing.data[0]

    # 같은 처리의 재요청은 성공으로 돌려준다.
    if report["status"] == body.status:
        return public_report(report)

    raise HTTPException(
        status_code=409,
        detail="Report already processed",
    )
# weavemo-backend-mock/routers/admin_notes.py
# 기존 코드 맨 아래에 추가

class ModerationActionRequest(BaseModel):
    action: Literal["warning", "messaging_restriction"]
    reason: str = Field(min_length=1, max_length=1000)
    internal_note: str = Field(default="", max_length=2000)
    duration_days: Literal[1, 3, 7] | None = None


@router.post("/note-reports/{report_id}/moderation")
def apply_note_moderation(
    body: ModerationActionRequest,
    report_id: int = Path(..., ge=1, le=MAX_BIGINT),
    admin=Depends(require_admin),
):
    reason = body.reason.strip()
    internal_note = body.internal_note.strip()

    if not reason:
        raise HTTPException(
            status_code=400,
            detail="A moderation reason is required",
        )

    if (
        body.action == "warning"
        and body.duration_days is not None
    ):
        raise HTTPException(
            status_code=400,
            detail="Warnings must not include a duration",
        )

    if (
        body.action == "messaging_restriction"
        and body.duration_days is None
    ):
        raise HTTPException(
            status_code=400,
            detail="A restriction duration is required",
        )

    try:
        result = get_supabase().rpc(
            "weavemo_apply_note_moderation",
            {
                # 관리자 ID는 요청 본문이 아닌 인증 결과를 사용한다.
                "p_admin": int(admin["user_id"]),
                "p_report_id": report_id,
                "p_action": body.action,
                "p_reason": reason,
                "p_internal_note": internal_note,
                "p_duration_days": body.duration_days,
            },
        ).execute()
    except Exception as error:
        logger.exception("Applying note moderation failed")

        raise HTTPException(
            status_code=503,
            detail="Could not confirm moderation result",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid moderation response",
        )

    errors = {
        "invalid_request": (
            400,
            "Invalid moderation request",
        ),
        "not_found": (
            404,
            "Report not found",
        ),
        "admin_required": (
            403,
            "Admin access required",
        ),
        "self_action_not_allowed": (
            403,
            "Cannot apply moderation to yourself",
        ),
        "report_changed": (
            409,
            "Report changed; refresh before continuing",
        ),
        "already_processed": (
            409,
            "Report already processed",
        ),
    }

    error_code = data.get("error")

    if error_code:
        status_code, detail = errors.get(
            error_code,
            (503, "Could not confirm moderation result"),
        )

        raise HTTPException(
            status_code=status_code,
            detail=detail,
        )

    action_id = data.get("id")

    valid_id = (
        isinstance(action_id, str)
        and action_id.isascii()
        and action_id.isdecimal()
        and len(action_id) <= 19
        and 0 < int(action_id) <= MAX_BIGINT
    )

    if (
        not valid_id
        or data.get("applied") is not True
        or data.get("report_id") != str(report_id)
        or data.get("action") != body.action
        or not isinstance(data.get("target_user_id"), str)
        or (
            body.action == "messaging_restriction"
            and not isinstance(data.get("expires_at"), str)
        )
        or (
            body.action == "warning"
            and data.get("expires_at") is not None
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid moderation response",
        )

    return {
        "id": action_id,
        "report_id": data["report_id"],
        "target_user_id": data["target_user_id"],
        "action": data["action"],
        "expires_at": data.get("expires_at"),
        "applied": True,
    }
# weavemo-backend-mock/routers/admin_notes.py
# 기존 코드 맨 아래에 추가

class RevokeModerationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


@router.post("/moderation-actions/{action_id}/revoke")
def revoke_moderation_action(
    body: RevokeModerationRequest,
    action_id: int = Path(..., ge=1, le=MAX_BIGINT),
    admin=Depends(require_admin),
):
    reason = body.reason.strip()

    if not reason:
        raise HTTPException(
            status_code=400,
            detail="A revocation reason is required",
        )

    try:
        result = get_supabase().rpc(
            "weavemo_revoke_moderation_action",
            {
                "p_admin": int(admin["user_id"]),
                "p_action_id": action_id,
                "p_reason": reason,
            },
        ).execute()
    except Exception as error:
        logger.exception("Revoking moderation action failed")

        raise HTTPException(
            status_code=503,
            detail="Could not confirm revocation result",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid revocation response",
        )

    errors = {
        "invalid_request": (400, "Invalid revocation request"),
        "not_found": (404, "Moderation action not found"),
        "admin_required": (403, "Admin access required"),
        "action_changed": (409, "Moderation action changed"),
        "not_a_restriction": (400, "This action is not a restriction"),
    }

    error_code = data.get("error")

    if error_code:
        status_code, detail = errors.get(
            error_code,
            (503, "Could not confirm revocation result"),
        )

        raise HTTPException(
            status_code=status_code,
            detail=detail,
        )

    if (
        data.get("id") != str(action_id)
        or data.get("revoked") is not True
        or not isinstance(data.get("revoked_at"), str)
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid revocation response",
        )

    return {
        "id": str(action_id),
        "revoked": True,
        "revoked_at": data["revoked_at"],
    }
# weavemo-backend-mock/routers/admin_notes.py
# 기존 코드 맨 아래에 추가

@router.get("/note-reports/{report_id}/moderation-actions")
def get_report_moderation_actions(
    report_id: int = Path(..., ge=1, le=MAX_BIGINT),
    admin=Depends(require_admin),
):
    supabase = get_supabase()

    try:
        report = (
            supabase.table("note_reports")
            .select("id")
            .eq("id", report_id)
            .limit(1)
            .execute()
        )

        if not report.data:
            raise HTTPException(
                status_code=404,
                detail="Report not found",
            )

        result = (
            supabase.table("moderation_actions")
            .select(
                "id, report_id, target_user_id, admin_user_id, "
                "action, reason, internal_note, created_at, "
                "expires_at, revoked_at, revoked_by, revoke_reason"
            )
            .eq("report_id", report_id)
            .order("id", desc=True)
            .execute()
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Moderation history lookup failed")

        raise HTTPException(
            status_code=503,
            detail="Could not load moderation history",
        ) from error

    items = []

    for row in result.data or []:
        items.append({
            "id": str(row["id"]),
            "report_id": str(row["report_id"]),
            "target_user_id": str(row["target_user_id"]),
            "admin_user_id": str(row["admin_user_id"]),
            "action": row["action"],
            "reason": row["reason"],
            "internal_note": row["internal_note"],
            "created_at": row["created_at"],
            "expires_at": row.get("expires_at"),
            "revoked_at": row.get("revoked_at"),
            "revoked_by": (
                str(row["revoked_by"])
                if row.get("revoked_by") is not None
                else None
            ),
            "revoke_reason": row.get("revoke_reason"),
        })

    return {"items": items}
