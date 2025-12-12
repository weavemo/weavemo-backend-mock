# routers/user.py
from fastapi import APIRouter, Depends
from dependencies.auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
def get_my_profile(current_user=Depends(get_current_user)):
    return {
        "user": current_user
    }
