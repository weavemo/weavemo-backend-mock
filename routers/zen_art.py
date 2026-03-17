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

    artworks = (
        supabase.table("zen_artworks")
        .select("*")
        .order("sort_order")
        .execute()
        .data
    )

    result = []

    for art in artworks:
        progress_res = (
            supabase.table("user_zen_art_progress")
            .select("*")
            .eq("user_id", user_id)
            .eq("artwork_id", art["id"])
            .execute()
        )

        if progress_res.data:
            progress = progress_res.data[0]
        else:
            progress = (
                supabase.table("user_zen_art_progress")
                .insert(
                    {
                        "user_id": user_id,
                        "artwork_id": art["id"],
                        "status": "locked",
                        "collected_fragments_count": 0,
                        "total_fragments_count": art["total_fragments"],
                        "completion_percent": 0,
                    }
                )
                .execute()
                .data[0]
            )

        result.append(
            {
                "code": art["code"],
                "title": art["title"],
                "status": progress["status"],
                "completion_percent": progress["completion_percent"],
                "collected_fragments_count": progress["collected_fragments_count"],
                "total_fragments_count": progress["total_fragments_count"],
            }
        )

    return {"items": result}


@router.post("/debug/add-fragment")
def add_fragment(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    art = (
        supabase.table("zen_artworks")
        .select("*")
        .eq("code", "crane_mist")
        .single()
        .execute()
        .data
    )

    fragment = (
        supabase.table("zen_fragments")
        .select("*")
        .eq("artwork_id", art["id"])
        .limit(1)
        .execute()
        .data[0]
    )

    user_frag_res = (
        supabase.table("user_zen_fragments")
        .select("*")
        .eq("user_id", user_id)
        .eq("fragment_id", fragment["id"])
        .execute()
    )

    if user_frag_res.data:
        current = user_frag_res.data[0]

        new_duplicate = (current.get("duplicate_count") or 0) + 1
        new_dust = (current.get("bonus_dust") or 0) + 10

        (
            supabase.table("user_zen_fragments")
            .update(
                {
                    "duplicate_count": new_duplicate,
                    "bonus_dust": new_dust,
                }
            )
            .eq("id", current["id"])
            .execute()
        )

        return {
            "message": "duplicate fragment",
            "fragment_code": fragment["code"],
            "is_duplicate": True,
            "duplicate_count": new_duplicate,
            "bonus_dust": new_dust,
        }

    (
        supabase.table("user_zen_fragments")
        .insert(
            {
                "user_id": user_id,
                "artwork_id": art["id"],
                "fragment_id": fragment["id"],
                "owned": True,
                "duplicate_count": 0,
                "bonus_dust": 0,
            }
        )
        .execute()
    )

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
    percent = (new_count / total) * 100 if total > 0 else 0

    status = "in_progress"
    if new_count >= total:
        status = "completed"

    (
        supabase.table("user_zen_art_progress")
        .update(
            {
                "collected_fragments_count": new_count,
                "completion_percent": percent,
                "status": status,
            }
        )
        .eq("id", progress["id"])
        .execute()
    )

    return {
        "message": "fragment added",
        "fragment_code": fragment["code"],
        "is_duplicate": False,
        "duplicate_count": 0,
        "bonus_dust": 0,
        "collected_fragments_count": new_count,
        "completion_percent": percent,
        "status": status,
    }


@router.post("/capsule/draw")
def draw_capsule(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    art = (
        supabase.table("zen_artworks")
        .select("*")
        .eq("code", "crane_mist")
        .single()
        .execute()
        .data
    )

    fragments = (
        supabase.table("zen_fragments")
        .select("*")
        .eq("artwork_id", art["id"])
        .execute()
        .data
    )

    # 유저가 가진 fragment 조회
    owned_rows = (
        supabase.table("user_zen_fragments")
        .select("fragment_id")
        .eq("user_id", user_id)
        .eq("artwork_id", art["id"])
        .execute()
        .data
    )

    owned_ids = {row["fragment_id"] for row in owned_rows}

    weights = []
    for f in fragments:
        base_weight = f.get("drop_weight", 100)

        if f["id"] in owned_ids:
            # 👉 중복이면 확률 낮춤 (핵심!)
            weights.append(int(base_weight * 0.3))
        else:
            # 👉 신규면 그대로
            weights.append(base_weight)

    fragment = random.choices(fragments, weights=weights, k=1)[0]
    user_frag_res = (
        supabase.table("user_zen_fragments")
        .select("*")
        .eq("user_id", user_id)
        .eq("fragment_id", fragment["id"])
        .execute()
    )

    is_duplicate = False
    duplicate_count = 0
    bonus_dust = 0

    if user_frag_res.data:
        is_duplicate = True
        current = user_frag_res.data[0]

        duplicate_count = (current.get("duplicate_count") or 0) + 1
        bonus_dust = (current.get("bonus_dust") or 0) + 10

        (
            supabase.table("user_zen_fragments")
            .update(
                {
                    "duplicate_count": duplicate_count,
                    "bonus_dust": bonus_dust,
                }
            )
            .eq("id", current["id"])
            .execute()
        )

        return {
            "artwork_code": art["code"],
            "fragment_code": fragment["code"],
            "is_duplicate": True,
            "duplicate_count": duplicate_count,
            "bonus_dust": bonus_dust,
        }

    (
        supabase.table("user_zen_fragments")
        .insert(
            {
                "user_id": user_id,
                "artwork_id": art["id"],
                "fragment_id": fragment["id"],
                "owned": True,
                "duplicate_count": 0,
                "bonus_dust": 0,
            }
        )
        .execute()
    )

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
    percent = (new_count / total) * 100 if total > 0 else 0

    status = "in_progress"
    if new_count >= total:
        status = "completed"

    (
        supabase.table("user_zen_art_progress")
        .update(
            {
                "collected_fragments_count": new_count,
                "completion_percent": percent,
                "status": status,
            }
        )
        .eq("id", progress["id"])
        .execute()
    )

    return {
        "artwork_code": art["code"],
        "fragment_code": fragment["code"],
        "is_duplicate": False,
        "duplicate_count": 0,
        "bonus_dust": 0,
        "collected_fragments_count": new_count,
        "completion_percent": percent,
        "status": status,
    }
