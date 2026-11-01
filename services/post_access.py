# C:\Users\myh03\project_weavemo\weavemo-backend-mock\services\post_access.py

from fastapi import HTTPException


def users_are_blocked(
    supabase,
    viewer_id: int,
    author_id: int,
) -> bool:
    """어느 한쪽이라도 상대를 차단했는지 검사한다."""
    if viewer_id == author_id:
        return False

    result = (
        supabase.table("user_blocks")
        .select("id")
        .or_(
            f"and(blocker_id.eq.{viewer_id},blocked_id.eq.{author_id}),"
            f"and(blocker_id.eq.{author_id},blocked_id.eq.{viewer_id})"
        )
        .limit(1)
        .execute()
    )

    return bool(result.data)


def users_are_friends(
    supabase,
    viewer_id: int,
    author_id: int,
) -> bool:
    """수락 완료된 기존 친구 관계를 검사한다."""
    if viewer_id == author_id:
        return False

    low_id, high_id = sorted((viewer_id, author_id))

    result = (
        supabase.table("friendships")
        .select("id")
        .eq("user_low_id", low_id)
        .eq("user_high_id", high_id)
        .eq("status", "accepted")
        .limit(1)
        .execute()
    )

    return bool(result.data)


def require_post_access(
    supabase,
    post_id: int,
    current_user: dict,
) -> dict:
    """
    접근 가능한 게시물만 반환한다.

    public: 로그인 사용자에게 허용하되 양방향 차단 적용
    friends: 작성자 또는 수락된 친구에게 허용
    private: 작성자만 허용
    deleted / 알 수 없는 공개 범위: 접근 불가
    """
    viewer_id = int(current_user["user_id"])

    result = (
        supabase.table("posts")
        .select("*")
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
    visibility = post.get("visibility")

    if visibility not in {"public", "friends", "private"}:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    author_id = int(post["user_id"])

    if viewer_id == author_id:
        return post

    if visibility == "private":
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    if users_are_blocked(supabase, viewer_id, author_id):
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    if visibility == "public":
        return post

    if users_are_friends(supabase, viewer_id, author_id):
        return post

    raise HTTPException(
        status_code=404,
        detail="Post not found",
    )
