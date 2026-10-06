# file: routers/collection.py

from fastapi import APIRouter, Depends, HTTPException
from db.database import get_supabase
from dependencies.auth import get_current_user
from services.collection_service import (
    get_collections,
    get_user_behaviors
)

router = APIRouter()

@router.get("")
def list_collections(user=Depends(get_current_user)):
    return get_collections(user["auth_uid"])


@router.get("/behaviors")
def behaviors(user=Depends(get_current_user)):
    return get_user_behaviors(user["user_id"])

@router.get("/dust")
def get_collection_dust(current_user=Depends(get_current_user)):
    supabase = get_supabase()

    result = (
        supabase.table("user_stats")
        .select("dust_balance")
        .eq("user_id", current_user["user_id"])
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="User stats not found")

    return {"dust_balance": result.data[0]["dust_balance"]}
