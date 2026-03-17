# weavemo-backend-mock/routers/zen_art.py

from fastapi import APIRouter, Depends
from db.database import get_supabase
from dependencies.auth import get_current_user

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
                "total_fragments_count": art["total_fragments"]
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
