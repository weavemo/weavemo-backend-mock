# weavemo-backend-mock/routers/posts.py
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError

from dependencies.auth import get_current_user
from dependencies.premium import require_premium
from db.database import get_supabase
from services.post_access import require_post_access

router = APIRouter()

ALLOWED_CATEGORIES = {"share", "question", "thanks"}
ALLOWED_VISIBILITIES = {"public", "friends", "private"}


def _preview(text: str | None, n: int = 120) -> str:
    if not text:
        return ""
    t = text.strip()
    return t if len(t) <= n else t[:n] + "…"


def _post_to_dto(p: dict, current_user: dict, *, include_content: bool) -> dict:
    is_anon = bool(p.get("is_anon"))
    is_mine = (p.get("user_id") == current_user["user_id"])

    dto = {
        "id": p.get("id"),
        "visibility": p.get("visibility"),
        "category": p.get("category"),
        "title": p.get("title"),
        "createdAt": p.get("created_at"),
        "authorDisplayName": "익명" if is_anon else "user",  # TODO: nickname
        "isAnonymous": is_anon,
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


@router.get("")
def list_posts(
    sort: str = "latest",
    category: str = "all",
    limit: int = 20,
    cursor: str | None = None,  # TODO: cursor 적용은 다음 단계에서 연결
    current_user=Depends(get_current_user),  # 로그인 필수
    supabase=Depends(get_supabase),
):
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="Invalid limit")

    if category != "all" and category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")

    query = supabase.table("posts").select(
        "id, user_id, category, title, content, created_at, is_anon, comments_count, likes_count, view_count, visibility"
    )

    if category != "all":
        query = query.eq("category", category)

    if sort == "latest":
        query = query.order("created_at", desc=True).order("id", desc=True)
        if cursor:
            # cursor = "{created_at}|{id}"
            try:
                c_created_at, c_id = cursor.split("|", 1)
                c_id = int(c_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid cursor")
            # created_at < c_created_at OR (created_at == c_created_at AND id < c_id)
            query = query.or_(
                f"created_at.lt.{c_created_at},and(created_at.eq.{c_created_at},id.lt.{c_id})"
            )    
    elif sort == "popular":
        query = (
            query.order("comments_count", desc=True)
            .order("created_at", desc=True)
            .order("id", desc=True)
        )
        if cursor:
            # cursor = "{comments_count}|{created_at}|{id}"
            try:
                c_comments, c_created_at, c_id = cursor.split("|", 2)
                c_comments = int(c_comments)
                c_id = int(c_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid cursor")
            # comments_count < c_comments
            # OR (comments_count==c_comments AND created_at < c_created_at)
            # OR (comments_count==c_comments AND created_at==c_created_at AND id < c_id)
            query = query.or_(
                f"comments_count.lt.{c_comments},"
                f"and(comments_count.eq.{c_comments},created_at.lt.{c_created_at}),"
                f"and(comments_count.eq.{c_comments},created_at.eq.{c_created_at},id.lt.{c_id})"
            )
    else:
        raise HTTPException(status_code=400, detail="Invalid sort")
    # 현재 목록은 공개글만 표시한다.
    query = query.eq("visibility", "public")

    # 내가 차단한 사용자와 나를 차단한 사용자를 모두 제외한다.
    user_id = int(current_user["user_id"])

    outgoing_blocks = (
        supabase.table("user_blocks")
        .select("blocked_id")
        .eq("blocker_id", user_id)
        .execute()
    )

    incoming_blocks = (
        supabase.table("user_blocks")
        .select("blocker_id")
        .eq("blocked_id", user_id)
        .execute()
    )

    blocked_ids = {
        int(row["blocked_id"])
        for row in (outgoing_blocks.data or [])
    }

    blocked_ids.update(
        int(row["blocker_id"])
        for row in (incoming_blocks.data or [])
    )

    if blocked_ids:
        query = query.not_.in_("user_id", sorted(blocked_ids))

    query = query.limit(limit)
    res = query.execute()
    rows = res.data or []

    # isLiked 배치 조회
    post_ids = [r["id"] for r in rows if r.get("id") is not None]
    liked_ids: set[int] = set()
    if post_ids:
        like_res = (
            supabase.table("post_likes")
            .select("post_id")
            .eq("user_id", current_user["user_id"])
            .in_("post_id", post_ids)
            .execute()
        )
        liked_ids = {x["post_id"] for x in (like_res.data or []) if x.get("post_id") is not None}

    for r in rows:
        r["_is_liked"] = (r.get("id") in liked_ids)

    items = [_post_to_dto(p, current_user, include_content=False) for p in rows]
    next_cursor = None
    if rows:
        last = rows[-1]
        if sort == "latest":
            next_cursor = f"{last['created_at']}|{last['id']}"
        else:
            next_cursor = f"{last['comments_count']}|{last['created_at']}|{last['id']}"

    return {"items": items, "nextCursor": next_cursor}


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
    if not (post_res.data or []):
        raise HTTPException(status_code=404, detail="Post not found")

    post = post_res.data[0]
    if post.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not allowed")

    if post.get("visibility") == "deleted":
        return {"deleted": True}

    supabase.table("posts").update(
        {"visibility": "deleted", "title": "(deleted)", "content": "[deleted]"}
    ).eq("id", post_id).execute()

    return {"deleted": True}
