# weavemo-backend-mock/routers/admin_notes.py

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

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
