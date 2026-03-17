# weavemo-backend-mock/routers/zen_art.py

from fastapi import APIRouter, Depends
from db.database import get_supabase
from dependencies.auth import get_current_user
import random

router = APIRouter(prefix="/zen-art", tags=["zen-art"])


@router.get("/gallery")
def get_gallery(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    # 1. 모든 작품 가져오기
    artworks = supabase.table("zen_artworks") \
        .select("*") \
        .order("sort_order") \
        .execute().data

    result = []

    for art in artworks:
        # 2. 유저 progress 조회
        progress_res = supabase.table("user_zen_art_progress") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("artwork_id", art["id"]) \
            .execute()

        if progress_res.data:
            progress = progress_res.data[0]
        else:
            # 3. 없으면 자동 생성
            progress = supabase.table("user_zen_art_progress").insert({
                "user_id": user_id,
                "artwork_id": art["id"],
                "status": "locked",
                "collected_fragments_count": 0,
                "total_fragments_count": art["total_fragments"],
                "completion_percent": 0
            }).execute().data[0]

        # 4. 응답 구성
        result.append({
            "code": art["code"],
            "title": art["title"],
            "status": progress["status"],
            "completion_percent": progress["completion_percent"],
            "collected_fragments_count": progress["collected_fragments_count"],
            "total_fragments_count": progress["total_fragments_count"]
        })

    return {
        "items": result
    }

@router.post("/debug/add-fragment")
def add_fragment(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    # 1. crane_mist 작품 가져오기
    art = supabase.table("zen_artworks") \
        .select("*") \
        .eq("code", "crane_mist") \
        .single() \
        .execute().data

    # 2. fragment 하나 가져오기 (예: 첫 번째)
    fragment = supabase.table("zen_fragments") \
        .select("*") \
        .eq("artwork_id", art["id"]) \
        .limit(1) \
        .execute().data[0]

    # 3. 유저 fragment 확인
    user_frag_res = supabase.table("user_zen_fragments") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("fragment_id", fragment["id"]) \
        .execute()

    if user_frag_res.data:
        # 이미 있으면 duplicate 증가
        supabase.table("user_zen_fragments") \
            .update({
                "duplicate_count": user_frag_res.data[0]["duplicate_count"] + 1
            }) \
            .eq("id", user_frag_res.data[0]["id"]) \
            .execute()
    else:
        # 없으면 새로 획득
        supabase.table("user_zen_fragments").insert({
            "user_id": user_id,
            "artwork_id": art["id"],
            "fragment_id": fragment["id"],
            "owned": True,
            "duplicate_count": 0
        }).execute()

        # progress 증가
        progress = supabase.table("user_zen_art_progress") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("artwork_id", art["id"]) \
            .single() \
            .execute().data

        new_count = progress["collected_fragments_count"] + 1
        total = progress["total_fragments_count"]
        percent = (new_count / total) * 100

        supabase.table("user_zen_art_progress") \
            .update({
                "collected_fragments_count": new_count,
                "completion_percent": percent,
                "status": "in_progress"
            }) \
            .eq("id", progress["id"]) \
            .execute()

    return {"message": "fragment added"}

@router.post("/capsule/draw")
def draw_capsule(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    # 1. 작품 선택 (지금은 crane만)
    art = (
        supabase.table("zen_artworks")
        .select("*")
        .eq("code", "crane_mist")
        .single()
        .execute()
        .data
    )

    # 2. fragment 전체 가져오기
    fragments = (
        supabase.table("zen_fragments")
        .select("*")
        .eq("artwork_id", art["id"])
        .execute()
        .data
    )

    # 3. 랜덤 선택
    fragment = random.choice(fragments)

    # 4. 이미 보유 확인
    user_frag_res = (
        supabase.table("user_zen_fragments")
        .select("*")
        .eq("user_id", user_id)
        .eq("fragment_id", fragment["id"])
        .execute()
    )

    is_duplicate = False

    if user_frag_res.data:
        # 👉 중복
        is_duplicate = True

        supabase.table("user_zen_fragments") \
            .update({
                "duplicate_count": user_frag_res.data[0]["duplicate_count"] + 1
            }) \
            .eq("id", user_frag_res.data[0]["id"]) \
            .execute()

    else:
        # 👉 신규 획득
        supabase.table("user_zen_fragments").insert({
            "user_id": user_id,
            "artwork_id": art["id"],
            "fragment_id": fragment["id"],
            "owned": True,
            "duplicate_count": 0
        }).execute()

        # progress 업데이트
        progress = (
            supabase.table("user_zen_art_progress")
            .select("*")
            .eq("user_id", user_id)
            .eq("artwork_id", art["id"])
            .single()
            .execute()
            .data
        )

        new_count = progress["collected_fragments_count"] + 1
        total = progress["total_fragments_count"]
        percent = (new_count / total) * 100

        status = "in_progress"
        if new_count >= total:
            status = "completed"

        supabase.table("user_zen_art_progress").update({
            "collected_fragments_count": new_count,
            "completion_percent": percent,
            "status": status
        }).eq("id", progress["id"]).execute()

    return {
        "artwork_code": art["code"],
        "fragment_code": fragment["code"],
        "is_duplicate": is_duplicate
    }
