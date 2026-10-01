# file: routers/collection.py

from fastapi import APIRouter, Depends
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
