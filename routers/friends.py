# weavemo-backend-mock/routers/friends.py

from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
)

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()

MAX_BIGINT = 9223372036854775807


def public_user(user: dict) -> dict:
    return {
        "id": str(user["id"]),
        "nickname": user.get("nickname") or "",
        "profile_image_url": user.get("profile_image_url"),
    }


def get_blocked_ids(
    supabase,
    user_id: int,
    candidate_ids: list[int],
) -> set[int]:
    if not candidate_ids:
        return set()

    outgoing = (
        supabase.table("user_blocks")
        .select("blocked_id")
        .eq("blocker_id", user_id)
        .in_("blocked_id", candidate_ids)
        .execute()
    )

    incoming = (
        supabase.table("user_blocks")
        .select("blocker_id")
        .eq("blocked_id", user_id)
        .in_("blocker_id", candidate_ids)
        .execute()
    )

    blocked = {
        row["blocked_id"]
        for row in outgoing.data or []
    }

    blocked.update(
        row["blocker_id"]
        for row in incoming.data or []
    )

    return blocked


def change_friendship(
    user_id: int,
    target_user_id: int,
    action: str,
) -> dict:
    supabase = get_supabase()

    result = supabase.rpc(
        "weavemo_friend_action",
        {
            "p_actor": user_id,
            "p_target": target_user_id,
            "p_action": action,
        },
    ).execute()

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Could not update friendship",
        )

    error = data.get("error")

    errors = {
        "self_not_allowed": (
            400,
            "Cannot send a friend request to yourself",
        ),
        "invalid_action": (
            400,
            "Invalid action",
        ),
        "not_found": (
            404,
            "User or friend request not found",
        ),
        "unavailable": (
            404,
            "User or friend request not found",
        ),
        "already_friends": (
            409,
            "Already friends",
        ),
        "incoming_request_exists": (
            409,
            "This user has already sent you a request",
        ),
        "not_allowed": (
            409,
            "This action is not available for the current request",
        ),
    }

    if error:
        status_code, detail = errors.get(
            error,
            (503, "Could not update friendship"),
        )

        raise HTTPException(
            status_code=status_code,
            detail=detail,
        )

    return data


def list_relationships(
    user_id: int,
    relationship_status: str,
    direction: str | None,
    limit: int,
    before_id: int | None,
) -> dict:
    supabase = get_supabase()

    query = (
        supabase.table("friendships")
        .select(
            "id, user_low_id, user_high_id, "
            "requested_by, status, created_at, accepted_at"
        )
        .eq("status", relationship_status)
        .or_(
            f"user_low_id.eq.{user_id},"
            f"user_high_id.eq.{user_id}"
        )
    )

    if direction == "incoming":
        query = query.neq("requested_by", user_id)
    elif direction == "outgoing":
        query = query.eq("requested_by", user_id)

    if before_id is not None:
        query = query.lt("id", before_id)

    result = (
        query.order("id", desc=True)
        .limit(limit + 1)
        .execute()
    )

    all_rows = result.data or []
    has_more = len(all_rows) > limit
    rows = all_rows[:limit]

    if not rows:
        return {
            "items": [],
            "next_cursor": None,
        }

    target_ids = [
        row["user_high_id"]
        if row["user_low_id"] == user_id
        else row["user_low_id"]
        for row in rows
    ]

    blocked_ids = get_blocked_ids(
        supabase,
        user_id,
        target_ids,
    )

    visible_ids = [
        target_id
        for target_id in target_ids
        if target_id not in blocked_ids
    ]

    users_by_id = {}

    if visible_ids:
        users_result = (
            supabase.table("users")
            .select("id, nickname, profile_image_url")
            .in_("id", visible_ids)
            .execute()
        )

        users_by_id = {
            user["id"]: user
            for user in users_result.data or []
        }

    items = []

    for row, target_id in zip(rows, target_ids):
        user = users_by_id.get(target_id)

        if user is None:
            continue

        items.append({
            **public_user(user),
            "friendship_id": str(row["id"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "accepted_at": row.get("accepted_at"),
        })

    # 차단으로 결과가 줄어도 원래 조회 위치 기준으로 페이지를 넘긴다.
    return {
        "items": items,
        "next_cursor": (
            str(rows[-1]["id"])
            if has_more
            else None
        ),
    }


@router.get("/search")
def search_users(
    q: str = Query(..., min_length=2, max_length=30),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]
    keyword = q.strip()

    if len(keyword) < 2:
        raise HTTPException(
            status_code=400,
            detail="Enter at least two characters",
        )

    escaped_keyword = (
        keyword.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )

    result = (
        supabase.table("users")
        .select("id, nickname, profile_image_url")
        .neq("id", user_id)
        .ilike("nickname", f"%{escaped_keyword}%")
        .order("nickname")
        .order("id")
        .limit(20)
        .execute()
    )

    candidates = result.data or []

    blocked_ids = get_blocked_ids(
        supabase,
        user_id,
        [user["id"] for user in candidates],
    )

    return {
        "items": [
            public_user(user)
            for user in candidates
            if user["id"] not in blocked_ids
        ]
    }


@router.get("")
def get_friends(
    limit: int = Query(20, ge=1, le=50),
    before_id: int | None = Query(
        None,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    return list_relationships(
        user_id=current_user["user_id"],
        relationship_status="accepted",
        direction=None,
        limit=limit,
        before_id=before_id,
    )


@router.get("/requests")
def get_friend_requests(
    direction: Literal["incoming", "outgoing"] = "incoming",
    limit: int = Query(20, ge=1, le=50),
    before_id: int | None = Query(
        None,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    return list_relationships(
        user_id=current_user["user_id"],
        relationship_status="pending",
        direction=direction,
        limit=limit,
        before_id=before_id,
    )


@router.post("/requests/{target_user_id}")
def send_friend_request(
    target_user_id: int = Path(
        ...,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    return change_friendship(
        current_user["user_id"],
        target_user_id,
        "request",
    )


@router.post("/requests/{target_user_id}/accept")
def accept_friend_request(
    target_user_id: int = Path(
        ...,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    return change_friendship(
        current_user["user_id"],
        target_user_id,
        "accept",
    )


@router.post("/requests/{target_user_id}/reject")
def reject_friend_request(
    target_user_id: int = Path(
        ...,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    return change_friendship(
        current_user["user_id"],
        target_user_id,
        "reject",
    )


@router.delete("/requests/{target_user_id}")
def cancel_friend_request(
    target_user_id: int = Path(
        ...,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    return change_friendship(
        current_user["user_id"],
        target_user_id,
        "cancel",
    )


@router.delete("/{target_user_id}")
def remove_friend(
    target_user_id: int = Path(
        ...,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    return change_friendship(
        current_user["user_id"],
        target_user_id,
        "remove",
    )
