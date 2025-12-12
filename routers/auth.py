# routers/auth.py
from fastapi import APIRouter, HTTPException, Depends
from schemas.auth import LoginRequest, RegisterRequest, AuthResponse
from core.supabase import supabase
from dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    res = supabase.auth.sign_up({
        "email": body.email,
        "password": body.password,
        "options": {
            "data": {
                "nickname": body.nickname
            }
        }
    })

    if not res.user or not res.session:
        raise HTTPException(status_code=400, detail="Registration failed")

    return {
        "user": {
            "id": res.user.id,
            "email": res.user.email,
            "nickname": res.user.user_metadata.get("nickname"),
        },
        "token": res.session.access_token,
        "expiresIn": res.session.expires_in,
    }


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    res = supabase.auth.sign_in_with_password({
        "email": body.email,
        "password": body.password,
    })

    if not res.user or not res.session:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "user": {
            "id": res.user.id,
            "email": res.user.email,
            "nickname": res.user.user_metadata.get("nickname"),
        },
        "token": res.session.access_token,
        "expiresIn": res.session.expires_in,
    }


@router.get("/profile")
def profile(current_user=Depends(get_current_user)):
    return {
        "user": current_user
        }
    
