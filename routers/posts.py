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
    items = res.data or []

    # 익명 표기 + isMine
    for p in items:
        p["isMine"] = (p.get("user_id") == current_user["user_id"])
        p["authorDisplayName"] = "익명" if p.get("is_anon") else "user"  # TODO: users.nickname 붙이기
        p["isAnonymous"] = bool(p.get("is_anon"))
        
    next_cursor = None
    if items:
        last = items[-1]
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
    data = {
        "user_id": current_user["user_id"],
        "category": body.get("category"),
        "title": body.get("title"),
        "content": body.get("content"),
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

    row["isMine"] = True
    row["authorDisplayName"] = "익명" if row.get("is_anon") else "user"
    row["isAnonymous"] = bool(row.get("is_anon"))
    return row


@router.get("/{post_id}")
def get_post_detail(
    post_id: int,
    current_user=Depends(get_current_user),  # 로그인 필수
    supabase=Depends(get_supabase),
):
    res = (
        supabase.table("posts")
        .select("id, user_id, category, title, content, created_at, is_anon, comments_count, likes_count, view_count, visibility")
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
    post["isMine"] = (post.get("user_id") == current_user["user_id"])
    post["authorDisplayName"] = "익명" if post.get("is_anon") else "user"
    post["isAnonymous"] = bool(post.get("is_anon"))
    return post
