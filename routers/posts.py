# weavemo-backend-mock/routers/posts.py
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException

from dependencies.auth import get_current_user
from dependencies.premium import require_premium
from db.database import get_supabase

router = APIRouter(prefix="/posts", tags=["posts"])

ALLOWED_CATEGORIES = {"share", "question", "thanks"}


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
    # 공개글만 (지금 정책: 읽기 로그인 필수지만 visibility는 public만 노출)
    query = query.eq("visibility", "public")

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
        "visibility": "public",
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
    res = (
        supabase.table("posts")
        .select("id, user_id, category, title, content, created_at, is_anon, comments_count, likes_count, view_count, visibility")
        .eq("id", post_id)
        .eq("visibility", "public")
        .limit(1)
        .execute()
    )

    if not res.data:
        raise HTTPException(status_code=404, detail="Post not found")

    post = res.data[0]

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
    post_res = (
        supabase.table("posts")
        .select("id, likes_count, visibility")
        .eq("id", post_id)
        .eq("visibility", "public")
        .limit(1)
        .execute()
    )
    if not (post_res.data or []):
        raise HTTPException(status_code=404, detail="Post not found")

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
        return {"liked": True}

    supabase.table("post_likes").insert(
        {"user_id": current_user["user_id"], "post_id": post_id}
    ).execute()

    new_lc = int(post_res.data[0].get("likes_count") or 0) + 1
    supabase.table("posts").update({"likes_count": new_lc}).eq("id", post_id).execute()
    return {"liked": True, "likesCount": new_lc}


# 🔹 DELETE /posts/{id}/like  (로그인만)
@router.delete("/{post_id}/like")
def unlike_post(
    post_id: int,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    post_res = (
        supabase.table("posts")
        .select("id, likes_count, visibility")
        .eq("id", post_id)
        .eq("visibility", "public")
        .limit(1)
        .execute()
    )
    if not (post_res.data or []):
        raise HTTPException(status_code=404, detail="Post not found")

    del_res = (
        supabase.table("post_likes")
        .delete()
        .eq("user_id", current_user["user_id"])
        .eq("post_id", post_id)
        .execute()
    )
    # 지운 게 없으면 멱등
    if not (del_res.data or []):
        return {"liked": False}

    new_lc = max(0, int(post_res.data[0].get("likes_count") or 0) - 1)
    supabase.table("posts").update({"likes_count": new_lc}).eq("id", post_id).execute()
    return {"liked": False, "likesCount": new_lc}


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

    if post.get("visibility") != "public":
        return {"deleted": True}

    supabase.table("posts").update(
        {"visibility": "deleted", "title": "(deleted)", "content": "[deleted]"}
    ).eq("id", post_id).execute()

    return {"deleted": True}
