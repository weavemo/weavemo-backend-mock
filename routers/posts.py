# weavemo-backend-mock/routers/posts.py
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException

from dependencies.auth import get_current_user
from dependencies.premium import require_premium
from db.database import get_supabase

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("")
def list_posts(
    sort: str = "latest",
    category: str = "all",
    limit: int = 20,
    cursor: str | None = None,  # TODO: cursor 적용은 다음 단계에서 연결
    current_user=Depends(get_current_user),  # 로그인 필수
    supabase=Depends(get_supabase),
):
    query = supabase.table("posts").select(
        "id, category, title, content, created_at, is_anonymous, comment_count, view_count, user_id"
    )

    if category != "all":
        query = query.eq("category", category)

    if sort == "latest":
        query = query.order("created_at", desc=True).order("id", desc=True)
    elif sort == "popular":
        query = (
            query.order("comment_count", desc=True)
            .order("created_at", desc=True)
            .order("id", desc=True)
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid sort")

    query = query.limit(limit)
    res = query.execute()
    items = res.data or []

    # 익명 표기 + isMine
    for p in items:
        p["isMine"] = (p.get("user_id") == current_user["user_id"])
        p["authorDisplayName"] = "익명" if p.get("is_anonymous") else "user"  # TODO: 닉네임 붙이기
        p["isAnonymous"] = bool(p.get("is_anonymous"))

    return {"items": items, "nextCursor": None}


@router.post("")
def create_post(
    body: dict,
    current_user=Depends(require_premium),  # 프리미엄만
    supabase=Depends(get_supabase),
):
    data = {
        "user_id": current_user["user_id"],
        "category": body.get("category"),
        "title": body.get("title"),
        "content": body.get("content"),
        "is_anonymous": bool(body.get("isAnonymous", False)),
        "created_at": datetime.utcnow().isoformat(),
        "comment_count": 0,
        "view_count": 0,
    }

    res = supabase.table("posts").insert(data).execute()
    row = (res.data or [None])[0]
    if not row:
        raise HTTPException(status_code=500, detail="Insert failed")

    row["isMine"] = True
    row["authorDisplayName"] = "익명" if row.get("is_anonymous") else "user"
    row["isAnonymous"] = bool(row.get("is_anonymous"))
    return row


@router.get("/{post_id}")
def get_post_detail(
    post_id: int,
    current_user=Depends(get_current_user),  # 로그인 필수
    supabase=Depends(get_supabase),
):
    res = (
        supabase.table("posts")
        .select("id, category, title, content, created_at, is_anonymous, comment_count, view_count, user_id")
        .eq("id", post_id)
        .limit(1)
        .execute()
    )

    if not res.data:
        raise HTTPException(status_code=404, detail="Post not found")

    post = res.data[0]

    # viewCount 옵션2: 유저/게시글/하루 1회만 +1
    today = date.today().isoformat()
    view_key = f"{current_user['user_id']}_{post_id}_{today}"

    view_res = (
        supabase.table("post_views")
        .select("id")
        .eq("view_key", view_key)
        .limit(1)
        .execute()
    )

    if not (view_res.data or []):
        supabase.table("post_views").insert({"view_key": view_key}).execute()
        supabase.table("posts").update({"view_count": (post.get("view_count") or 0) + 1}).eq("id", post_id).execute()
        post["view_count"] = (post.get("view_count") or 0) + 1

    post["isMine"] = (post.get("user_id") == current_user["user_id"])
    post["authorDisplayName"] = "익명" if post.get("is_anonymous") else "user"
    post["isAnonymous"] = bool(post.get("is_anonymous"))
    return post
