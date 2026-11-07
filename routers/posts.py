# weavemo-backend-mock/routers/posts.py

from time import perf_counter
from datetime import datetime, date
from postgrest.exceptions import APIError
from services.hidden_content import get_hidden_content_ids
from dependencies.auth import get_current_user
from dependencies.premium import require_premium
from db.database import get_supabase
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from services.post_access import (
    require_post_access,
    users_are_blocked,
    users_are_friends,
)

router = APIRouter()

ALLOWED_CATEGORIES = {"share", "question", "thanks"}
ALLOWED_VISIBILITIES = {"public", "friends", "private"}


def _preview(text: str | None, n: int = 120) -> str:
    if not text:
        return ""
    t = text.strip()
    return t if len(t) <= n else t[:n] + "…"


def _attach_author_names(supabase, rows: list[dict]) -> None:
    author_ids = {
        int(row["user_id"])
        for row in rows
        if not row.get("is_anon") and row.get("user_id") is not None
    }

    authors = {}
    if author_ids:
        result = (
            supabase.table("users")
            .select("id, nickname, profile_image_url")
            .in_("id", sorted(author_ids))
            .execute()
        )
        authors = {int(user["id"]): user for user in result.data or []}

    for row in rows:
        if row.get("is_anon"):
            row["_author_name"] = "익명"
            row["_author_avatar_url"] = None
            continue

        user_id = row.get("user_id")
        author = authors.get(int(user_id), {}) if user_id is not None else {}
        row["_author_name"] = (author.get("nickname") or "").strip() or "user"
        row["_author_avatar_url"] = author.get("profile_image_url")

# 조회 권한이 확인된 게시물들의 사진 유무를 한 번에 확인한다.
def _attach_photo_flags(supabase, rows: list[dict]) -> None:
    post_ids = [
        int(row["id"])
        for row in rows
        if row.get("id") is not None
    ]

    photo_post_ids = set()

    if post_ids:
        result = (
            supabase.table("post_media")
            .select("post_id")
            .in_("post_id", post_ids)
            .execute()
        )

        photo_post_ids = {
            int(media["post_id"])
            for media in (result.data or [])
        }

    for row in rows:
        row["_has_photo"] = (
            row.get("id") is not None
            and int(row["id"]) in photo_post_ids
        )

def _post_to_dto(p: dict, current_user: dict, *, include_content: bool) -> dict:
    is_anon = bool(p.get("is_anon"))
    is_mine = (p.get("user_id") == current_user["user_id"])

    dto = {
        "id": p.get("id"),
        "visibility": p.get("visibility"),
        "hasPhoto": bool(p.get("_has_photo", False)),
        "category": p.get("category"),
        "title": p.get("title"),
        "createdAt": p.get("created_at"),
        "authorDisplayName": (
            "익명" if is_anon else p.get("_author_name", "user")
        ),
        "isAnonymous": is_anon,
        "authorAvatarUrl": None if is_anon else p.get("_author_avatar_url"),
        "authorUserId": str(p["user_id"]) if not is_anon and p.get("user_id") is not None else None,
        "isMine": is_mine,
        "commentCount": p.get("comments_count", 0),
        "likesCount": p.get("likes_count", 0),
        "viewCount": p.get("view_count", 0),
        "isLiked": bool(p.get("_is_liked", False)),
    }

    if include_content:
        dto["content"] = p.get("content") or ""
    else:
        dto["contentPreview"] = _preview(p.get("content"))

    return dto

def _recalc_likes_count(supabase, post_id: int) -> int:
    """
    likes_count를 posts 테이블에 저장해두는 구조라면,
    동시성/재시도에도 안전하게 '진짜' likes 수로 다시 맞춘다.
    """
    cnt_res = (
        supabase.table("post_likes")
        .select("post_id", count="exact")
        .eq("post_id", post_id)
        .execute()
    )
    # postgrest response에 count가 있을 수도/없을 수도 있어서 안전 처리
    likes_count = int(getattr(cnt_res, "count", None) or 0)
    supabase.table("posts").update({"likes_count": likes_count}).eq("id", post_id).execute()
    return likes_count


@router.get("/people/{user_id}")
def get_community_profile(
    user_id: int = Path(..., ge=1, le=9223372036854775807),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    viewer_id = int(current_user["user_id"])

    if users_are_blocked(supabase, viewer_id, user_id):
        raise HTTPException(status_code=404, detail="Author not available")

    result = (
        supabase.table("users")
        .select("id, nickname, profile_image_url")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Author not available")

    author = result.data[0]
    return {
        "userId": str(author["id"]),
        "nickname": author.get("nickname"),
        "profileImageUrl": author.get("profile_image_url"),
    }

@router.get("")
def list_posts(
    sort: str = "latest",
    category: str = "all",
    feed: str = "public",
    limit: int = 20,
    cursor: str | None = None,
    author_user_id: int | None = Query(
        default=None,
        ge=1,
        le=9223372036854775807,
    ),
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    if feed not in {"public", "friends", "mine"}:
        raise HTTPException(status_code=400, detail="Invalid feed")

    if sort not in {"latest", "popular"}:
        raise HTTPException(status_code=400, detail="Invalid sort")

    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="Invalid limit")

    if category != "all" and category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")

    started = perf_counter()

    try:
        result = supabase.rpc(
            "get_community_feed_page",
            {
                "p_user_id": int(current_user["user_id"]),
                "p_feed": feed,
                "p_category": category,
                "p_sort": sort,
                "p_limit": limit,
                "p_cursor": cursor,
                "p_author_user_id": author_user_id,
            },
        ).execute()
    except APIError as error:
        known_errors = {
            "invalid_feed_request": (400, "Invalid feed request"),
            "invalid_cursor": (400, "Invalid cursor"),
            "author_not_available": (404, "Author not available"),
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

        raise HTTPException(
            status_code=503,
            detail="Could not load community feed",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid community feed response",
        )

    rows = data.get("items")
    next_cursor = data.get("nextCursor")

    if (
        not isinstance(rows, list)
        or any(
            not isinstance(row, dict)
            or row.get("id") is None
            or row.get("user_id") is None
            for row in rows
        )
        or (
            next_cursor is not None
            and not isinstance(next_cursor, str)
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Invalid community feed response",
        )

    items = [
        _post_to_dto(
            row,
            current_user,
            include_content=False,
        )
        for row in rows
    ]

    print(
        f"[posts timing] feed={feed} "
        f"rpc_and_format={(perf_counter() - started) * 1000:.1f}ms",
        flush=True,
    )

    return {
        "items": items,
        "nextCursor": next_cursor,
    }

@router.post("")
def create_post(
    body: dict,
    current_user=Depends(require_premium),  # 프리미엄만
    supabase=Depends(get_supabase),
):

    # 기존 클라이언트가 공개 범위를 보내지 않으면 public을 유지한다.
    visibility = body.get("visibility", "public")

    if (
        not isinstance(visibility, str)
        or visibility not in ALLOWED_VISIBILITIES
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid visibility",
        )
    category = body.get("category")
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content required")
    if len(title) > 80:
        raise HTTPException(status_code=400, detail="Title too long")
    if len(content) > 2000:
        raise HTTPException(status_code=400, detail="Content too long") 
    
    data = {
        "user_id": current_user["user_id"],
        "category": category,
        "title": title,
        "content": content,
        "is_anon": bool(body.get("isAnonymous", False)),
        "visibility": visibility,
        "created_at": datetime.utcnow().isoformat(),
        "comments_count": 0,
        "likes_count": 0,
        "view_count": 0,
    }

    res = supabase.table("posts").insert(data).execute()
    row = (res.data or [None])[0]
    if not row:
        raise HTTPException(status_code=500, detail="Insert failed")

    _attach_author_names(supabase, [row])
    return _post_to_dto(row, current_user, include_content=True)


@router.get("/{post_id}")
def get_post_detail(
    post_id: int,
    current_user=Depends(get_current_user),  # 로그인 필수
    supabase=Depends(get_supabase),
):
    post = require_post_access(
        supabase,
        post_id,
        current_user,
    )

    # viewCount 옵션2: 유저/게시글/하루 1회만 +1
    today = date.today().isoformat()
    view_res = (
        supabase.table("post_views")
        .select("id")
        .eq("user_id", current_user["user_id"])
        .eq("post_id", post_id)
        .eq("viewed_on", today)
        .limit(1)
        .execute()
    )

    if not (view_res.data or []):
        supabase.table("post_views").insert({
            "user_id": current_user["user_id"],
            "post_id": post_id,
            "viewed_on": today,
        }).execute()
        new_vc = (post.get("view_count") or 0) + 1
        supabase.table("posts").update({"view_count": new_vc}).eq("id", post_id).execute()
        post["view_count"] = new_vc
    # isLiked 단건 조회
    like_res = (
        supabase.table("post_likes")
        .select("post_id")
        .eq("user_id", current_user["user_id"])
        .eq("post_id", post_id)
        .limit(1)
        .execute()
    )
    post["_is_liked"] = bool(like_res.data or [])

    _attach_author_names(supabase, [post])
    _attach_photo_flags(supabase, [post])
    return _post_to_dto(post, current_user, include_content=True)


# 🔹 POST /posts/{id}/like  (로그인만)
@router.post("/{post_id}/like")
def like_post(
    post_id: int,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    # 공개글만
    require_post_access(
        supabase,
        post_id,
        current_user,
    )

    # 이미 좋아요면 멱등
    exist = (
        supabase.table("post_likes")
        .select("post_id")
        .eq("user_id", current_user["user_id"])
        .eq("post_id", post_id)
        .limit(1)
        .execute()
    )
    if exist.data:
        # 카운트도 안전하게 맞춰서 내려주기(프론트가 즉시 반영 가능)
        lc = _recalc_likes_count(supabase, post_id)
        return {"liked": True, "likesCount": lc}

    # insert는 경쟁조건/재시도에서 중복 유니크 에러가 날 수 있으니 멱등 처리
    try:
        supabase.table("post_likes").insert(
            {"user_id": current_user["user_id"], "post_id": post_id}
        ).execute()
    except APIError as e:
        if e.code != "23505":
            raise

    lc = _recalc_likes_count(supabase, post_id)
    return {"liked": True, "likesCount": lc}


# 🔹 DELETE /posts/{id}/like  (로그인만)
@router.delete("/{post_id}/like")
def unlike_post(
    post_id: int,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    require_post_access(
        supabase,
        post_id,
        current_user,
    )

    del_res = (
        supabase.table("post_likes")
        .delete()
        .eq("user_id", current_user["user_id"])
        .eq("post_id", post_id)
        .execute()
    )
    # 지운 게 없으면 멱등
    if not (del_res.data or []):
        lc = _recalc_likes_count(supabase, post_id)
        return {"liked": False, "likesCount": lc}

    lc = _recalc_likes_count(supabase, post_id)
    return {"liked": False, "likesCount": lc}


# 🔹 DELETE /posts/{id}  (작성자만) - 안전하게 soft delete
# 게시물 작성자만 글을 삭제하고 연결된 사진을 정리한다.
@router.delete("/{post_id}")
def delete_post(
    post_id: int,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    post_res = (
        supabase.table("posts")
        .select("id, user_id, visibility")
        .eq("id", post_id)
        .limit(1)
        .execute()
    )

    if not post_res.data:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    post = post_res.data[0]

    if int(post["user_id"]) != int(current_user["user_id"]):
        raise HTTPException(
            status_code=403,
            detail="Not allowed",
        )

    # 사진 정리가 실패하더라도 글과 사진에 대한 접근은 먼저 막는다.
    if post.get("visibility") != "deleted":
        supabase.table("posts").update({
            "visibility": "deleted",
            "title": "(deleted)",
            "content": "[deleted]",
        }).eq("id", post_id).execute()

    # 이미 삭제된 글도 남은 사진 정리를 다시 시도한다.
    media_res = (
        supabase.table("post_media")
        .select("id, storage_path")
        .eq("post_id", post_id)
        .execute()
    )

    for media in media_res.data or []:
        try:
            # 파일 삭제에 성공한 뒤에만 연결 정보를 제거한다.
            supabase.storage.from_("post-media").remove(
                [media["storage_path"]]
            )

            supabase.table("post_media").delete().eq(
                "id", media["id"]
            ).eq("post_id", post_id).execute()
        except Exception:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Post hidden but image cleanup incomplete; "
                    "retry deleting the post"
                ),
            )

    return {"deleted": True}
# 게시물 작성자만 허용된 항목을 수정할 수 있다.
@router.patch("/{post_id}")
def update_post(
    post_id: int,
    body: dict,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    result = (
        supabase.table("posts")
        .select("id, user_id, visibility")
        .eq("id", post_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    post = result.data[0]

    if int(post["user_id"]) != int(current_user["user_id"]):
        raise HTTPException(
            status_code=403,
            detail="Not allowed",
        )

    if post.get("visibility") == "deleted":
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    allowed_fields = {
        "title",
        "content",
        "category",
        "isAnonymous",
        "visibility",
    }

    if not body or set(body) - allowed_fields:
        raise HTTPException(
            status_code=400,
            detail="Invalid update fields",
        )

    changes = {}

    # 문자열 형식과 길이를 서버에서도 검사한다.
    for field, max_length in (("title", 80), ("content", 2000)):
        if field not in body:
            continue

        value = body[field]

        if not isinstance(value, str):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {field}",
            )

        value = value.strip()

        if field == "content" and not value:
            raise HTTPException(
                status_code=400,
                detail="Content required",
            )

        if len(value) > max_length:
            raise HTTPException(
                status_code=400,
                detail=f"{field} too long",
            )

        changes[field] = value

    if "category" in body:
        value = body["category"]

        if not isinstance(value, str) or value not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail="Invalid category",
            )

        changes["category"] = value

    if "visibility" in body:
        value = body["visibility"]

        if not isinstance(value, str) or value not in ALLOWED_VISIBILITIES:
            raise HTTPException(
                status_code=400,
                detail="Invalid visibility",
            )

        changes["visibility"] = value

    if "isAnonymous" in body:
        if not isinstance(body["isAnonymous"], bool):
            raise HTTPException(
                status_code=400,
                detail="Invalid anonymous setting",
            )

        changes["is_anon"] = body["isAnonymous"]

    changes["updated_at"] = datetime.utcnow().isoformat()

    # 삭제된 게시물이 동시 수정 요청으로 복구되지 않도록 조건을 유지한다.
    updated = (
        supabase.table("posts")
        .update(changes)
        .eq("id", post_id)
        .eq("user_id", current_user["user_id"])
        .neq("visibility", "deleted")
        .execute()
    )

    if not updated.data:
        raise HTTPException(
            status_code=409,
            detail="Post changed or is no longer available",
        )

    row = updated.data[0]
    _attach_author_names(supabase, [row])
    _attach_photo_flags(supabase, [row])

    return _post_to_dto(
        row,
        current_user,
        include_content=True,
    )
