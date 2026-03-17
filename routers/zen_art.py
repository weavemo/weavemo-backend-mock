# weavemo-backend-mock/routers/zen_art.py

from fastapi import APIRouter, Depends
from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter(prefix="/zen-art", tags=["zen-art"])


@router.get("/gallery")
def get_gallery(current_user=Depends(get_current_user)):
    supabase = get_supabase()

    res = supabase.table("zen_artworks") \
        .select("*") \
        .order("sort_order") \
        .execute()

    return {
        "items": res.data
    }
