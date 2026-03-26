# file: routers/collection.py

from fastapi import APIRouter, Depends
from dependencies.auth import get_current_user
from services.collection_service import (
    complete_action,
    get_collections,
    get_user_behaviors
)

router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("/complete")
def complete(collection_key: str, user=Depends(get_current_user)):
    return complete_action(user["user_id"], collection_key)


@router.get("")
def list_collections(user=Depends(get_current_user)):
    return get_collections(user["user_id"])


@router.get("/behaviors")
def behaviors(user=Depends(get_current_user)):
    return get_user_behaviors(user["user_id"])
