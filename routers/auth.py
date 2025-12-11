
from fastapi import APIRouter, HTTPException
from schemas.auth import LoginRequest, RegisterRequest, AuthResponse
from models.user import User
from db.fake_db import fake_users, current_id

router = APIRouter()

@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    global current_id

    if body.email in fake_users:
        raise HTTPException(400, "Email already exists")

    user = User(id=current_id, email=body.email, password=body.password, nickname=body.nickname)
    fake_users[body.email] = user
    current_id += 1

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "nickname": user.nickname
        },
        "token": "mock_access_token",
        "refreshToken": "mock_refresh_token"
    }

@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    if body.email not in fake_users:
        raise HTTPException(400, "User not found")

    user = fake_users[body.email]

    if user.password != body.password:
        raise HTTPException(401, "Invalid password")

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "nickname": user.nickname
        },
        "token": "mock_access_token",
        "refreshToken": "mock_refresh_token"
    }
