from fastapi import APIRouter, HTTPException, Depends, status
from schemas.auth import LoginRequest, RegisterRequest, AuthResponse
from core.supabase import get_supabase
from dependencies.auth import get_current_user
from supabase_auth.errors import AuthApiError

router = APIRouter()


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    supabase = get_supabase()

    try:
        res = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {
                "data": {
                    "nickname": body.nickname
                }
            }
        })
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not res.user or not res.session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed",
        )

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
    supabase = get_supabase()

    try:
        res = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not res.user or not res.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login failed",
        )

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
    return {"user": current_user}
