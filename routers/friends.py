# weavemo-backend-mock/routers/friends.py

from typing import Literal
from services.reward_ownership import (
    owned_reward_keys,
    valid_equipped_frame,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
)
from services.reward_ownership import (
    owned_reward_keys,
    valid_equipped_frame,
    profile_equipment_by_user,
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
            .select("id, nickname, profile_image_url, auth_uid")
            .in_("id", visible_ids)
            .execute()
        )

        users_by_id = {
            user["id"]: user
            for user in users_result.data or []
        }

    equipment_by_id = profile_equipment_by_user(
        supabase,
        list(users_by_id.values()),
    )
    items = []

    for row, target_id in zip(rows, target_ids):
        user = users_by_id.get(target_id)

        if user is None:
            continue

        items.append({
            **public_user(user),
            **equipment_by_id.get(target_id, {}),
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

# weavemo-backend-mock/routers/friends.py
# @router.get("/search") 바로 위에 추가

@router.get("/discover")
def discover_users(
    q: str | None = Query(None, max_length=30),
    limit: int = Query(20, ge=1, le=50),
    before_id: int | None = Query(
        None,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = int(current_user["user_id"])
    keyword = (q or "").strip()

    query = (
        supabase.table("users")
        .select(
            "id, nickname, profile_image_url, "
            "auth_uid, note_receive_scope"
        )
        .neq("id", user_id)
    )

    if keyword:
        escaped_keyword = (
            keyword.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

        query = query.ilike(
            "nickname",
            f"%{escaped_keyword}%",
        )

    if before_id is not None:
        query = query.lt("id", before_id)

    result = (
        query.order("id", desc=True)
        .limit(limit + 1)
        .execute()
    )

    all_rows = result.data or []
    rows = all_rows[:limit]
    has_more = len(all_rows) > limit

    if not rows:
        return {
            "items": [],
            "next_cursor": None,
        }

    blocked_ids = get_blocked_ids(
        supabase,
        user_id,
        [user["id"] for user in rows],
    )

    visible_users = [
        user
        for user in rows
        if user["id"] not in blocked_ids
    ]

    relationships = {}
    note_requests = {}

    if visible_users:
        visible_ids = [
            user["id"]
            for user in visible_users
        ]

        low_side = (
            supabase.table("friendships")
            .select(
                "user_low_id, user_high_id, "
                "requested_by, status"
            )
            .eq("user_low_id", user_id)
            .in_("user_high_id", visible_ids)
            .execute()
        )

        high_side = (
            supabase.table("friendships")
            .select(
                "user_low_id, user_high_id, "
                "requested_by, status"
            )
            .eq("user_high_id", user_id)
            .in_("user_low_id", visible_ids)
            .execute()
        )

        for row in (
            (low_side.data or [])
            + (high_side.data or [])
        ):
            target_id = (
                row["user_high_id"]
                if row["user_low_id"] == user_id
                else row["user_low_id"]
            )

            if row["status"] == "accepted":
                relationships[target_id] = "friends"
            elif row["status"] == "pending":
                relationships[target_id] = (
                    "outgoing"
                    if row["requested_by"] == user_id
                    else "incoming"
                )

        requests_low = (
            supabase.table("friend_note_requests")
            .select(
                "user_low_id, user_high_id, "
                "requested_by, status"
            )
            .eq("user_low_id", user_id)
            .in_("user_high_id", visible_ids)
            .execute()
        )

        requests_high = (
            supabase.table("friend_note_requests")
            .select(
                "user_low_id, user_high_id, "
                "requested_by, status"
            )
            .eq("user_high_id", user_id)
            .in_("user_low_id", visible_ids)
            .execute()
        )

        for row in (
            (requests_low.data or [])
            + (requests_high.data or [])
        ):
            target_id = (
                row["user_high_id"]
                if row["user_low_id"] == user_id
                else row["user_low_id"]
            )

            status = row["status"]

            if status == "pending":
                status = (
                    "outgoing"
                    if row["requested_by"] == user_id
                    else "incoming"
                )

            note_requests[target_id] = status

    equipment_by_id = profile_equipment_by_user(
        supabase,
        visible_users,
    )

    items = []

    for user in visible_users:
        target_id = user["id"]
        relationship = relationships.get(
            target_id,
            "none",
        )
        note_status = note_requests.get(target_id)

        # 기존에 수락한 쪽지 연결은 수신 범위를 바꿔도 유지한다.
        can_send_note = (
            relationship == "friends"
            or note_status == "accepted"
            or (
                note_status is None
                and user.get("note_receive_scope") == "requests"
            )
        )

        items.append({
            **public_user(user),
            **equipment_by_id.get(target_id, {}),
            "relationship": relationship,
            "note_request_status": note_status,
            "can_send_note": can_send_note,
        })

    return {
        "items": items,
        # 차단으로 목록이 줄어도 조회 위치를 유지한다.
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

    if not candidates:
        return {"items": []}

    blocked_ids = get_blocked_ids(
        supabase,
        user_id,
        [user["id"] for user in candidates],
    )

    visible_users = [
        user
        for user in candidates
        if user["id"] not in blocked_ids
    ]

    if not visible_users:
        return {"items": []}

    visible_ids = [
        user["id"]
        for user in visible_users
    ]

    low_side = (
        supabase.table("friendships")
        .select(
            "user_low_id, user_high_id, "
            "requested_by, status"
        )
        .eq("user_low_id", user_id)
        .in_("user_high_id", visible_ids)
        .execute()
    )

    high_side = (
        supabase.table("friendships")
        .select(
            "user_low_id, user_high_id, "
            "requested_by, status"
        )
        .eq("user_high_id", user_id)
        .in_("user_low_id", visible_ids)
        .execute()
    )

    relationships = {}

    for row in (
        (low_side.data or [])
        + (high_side.data or [])
    ):
        target_id = (
            row["user_high_id"]
            if row["user_low_id"] == user_id
            else row["user_low_id"]
        )

        if row["status"] == "accepted":
            relationships[target_id] = "friends"
        elif row["requested_by"] == user_id:
            relationships[target_id] = "outgoing"
        else:
            relationships[target_id] = "incoming"

    return {
        "items": [
            {
                **public_user(user),
                "relationship": relationships.get(
                    user["id"],
                    "none",
                ),
            }
            for user in visible_users
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

@router.get("/requests/count")
def get_friend_request_count(
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()

    result = supabase.rpc(
        "weavemo_friend_request_count",
        {"p_user_id": current_user["user_id"]},
    ).execute()

    return {"count": int(result.data)}

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
# 차단 관리


def change_user_block(
    user_id: int,
    target_user_id: int,
    action: str,
) -> dict:
    supabase = get_supabase()

    result = supabase.rpc(
        "weavemo_block_action",
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
            detail="Could not update block",
        )

    error = data.get("error")

    errors = {
        "self_not_allowed": (
            400,
            "Cannot block yourself",
        ),
        "invalid_action": (
            400,
            "Invalid action",
        ),
        "not_found": (
            404,
            "User not found",
        ),
    }

    if error:
        status_code, detail = errors.get(
            error,
            (503, "Could not update block"),
        )

        raise HTTPException(
            status_code=status_code,
            detail=detail,
        )

    if not isinstance(data.get("blocked"), bool):
        raise HTTPException(
            status_code=503,
            detail="Invalid block response",
        )

    return data


@router.get("/blocks")
def get_my_blocks(
    limit: int = Query(20, ge=1, le=50),
    before_id: int | None = Query(
        None,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    query = (
        supabase.table("user_blocks")
        .select("id, blocked_id, created_at")
        .eq("blocker_id", user_id)
    )

    if before_id is not None:
        query = query.lt("id", before_id)

    result = (
        query.order("id", desc=True)
        .limit(limit + 1)
        .execute()
    )

    all_rows = result.data or []
    rows = all_rows[:limit]
    has_more = len(all_rows) > limit

    if not rows:
        return {
            "items": [],
            "next_cursor": None,
        }

    users_result = (
        supabase.table("users")
        .select("id, nickname, profile_image_url")
        .in_(
            "id",
            [row["blocked_id"] for row in rows],
        )
        .execute()
    )

    users_by_id = {
        user["id"]: user
        for user in users_result.data or []
    }

    items = []

    for row in rows:
        user = users_by_id.get(row["blocked_id"])

        if user is None:
            continue

        items.append({
            **public_user(user),
            "block_id": str(row["id"]),
            "created_at": row["created_at"],
        })

    return {
        "items": items,
        "next_cursor": (
            str(rows[-1]["id"])
            if has_more
            else None
        ),
    }


@router.post("/blocks/{target_user_id}")
def block_user(
    target_user_id: int = Path(
        ...,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    return change_user_block(
        current_user["user_id"],
        target_user_id,
        "block",
    )


@router.delete("/blocks/{target_user_id}")
def unblock_user(
    target_user_id: int = Path(
        ...,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    return change_user_block(
        current_user["user_id"],
        target_user_id,
        "unblock",
    )
# weavemo-backend-mock/routers/friends.py
# 기존 코드 맨 아래에 추가

# weavemo-backend-mock/routers/friends.py
# 기존 get_friend_profile 함수 교체

# weavemo-backend-mock/routers/friends.py
# 기존 get_friend_profile 함수 교체

@router.get("/{target_user_id}/profile")
def get_friend_profile(
    target_user_id: int = Path(
        ...,
        ge=1,
        le=MAX_BIGINT,
    ),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = int(current_user["user_id"])

    relationship = (
        supabase.table("friendships")
        .select("id")
        .eq("user_low_id", min(user_id, target_user_id))
        .eq("user_high_id", max(user_id, target_user_id))
        .eq("status", "accepted")
        .limit(1)
        .execute()
    )

    blocked_ids = get_blocked_ids(
        supabase,
        user_id,
        [target_user_id],
    )

    if not relationship.data or target_user_id in blocked_ids:
        raise HTTPException(
            status_code=404,
            detail="Friend not available",
        )

    result = (
        supabase.table("users")
        .select("id, nickname, profile_image_url, auth_uid")
        .eq("id", target_user_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Friend not available",
        )

    target_user = result.data[0]

    stats_result = (
        supabase.table("user_stats")
        .select("equipped_frame, equipped_badge")
        .eq("user_id", target_user_id)
        .limit(1)
        .execute()
    )

    stats = (
        stats_result.data[0]
        if stats_result.data
        else {}
    )

    auth_uid = target_user.get("auth_uid")

    owned = (
        owned_reward_keys(supabase, auth_uid)
        if auth_uid
        else set()
    )

    return {
        # auth_uid는 응답에 포함하지 않는다.
        **public_user(target_user),
        "equipped_frame": valid_equipped_frame(
            stats.get("equipped_frame"),
            owned,
        ),
        "equipped_badge": stats.get("equipped_badge"),
    }
