from fastapi import APIRouter
from db.fake_db import fake_users

router = APIRouter()

@router.get("/profile")
def profile():
    # 그냥 첫 유저 반환 (mock)
    for email, user in fake_users.items():
        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "nickname": user.nickname
            }
        }
    return {"user": None}

