import httpx

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from supabase_auth.errors import AuthApiError

from schemas.auth import LoginRequest, RegisterRequest, AuthResponse
from core.supabase import get_supabase
from dependencies.auth import get_current_user
from config.settings import settings


router = APIRouter()
bearer = HTTPBearer()

# 로컬 개발용. 배포 시 실제 프론트엔드 주소로 변경.
RESET_URL = "http://www.localhost:5173/reset-password"


class RecoveryRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    new_password: str


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    supabase = get_supabase()

    try:
        res = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {
                "data": {
                    "nickname": body.nickname,
                }
            },
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
    except AuthApiError:
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
        "refreshToken": res.session.refresh_token,
    }


@router.get("/profile")
def profile(current_user=Depends(get_current_user)):
    return {"user": current_user}


@router.post("/password/recovery")
def request_password_recovery(body: RecoveryRequest):
    email = body.email.strip()

    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email",
        )

    try:
        response = httpx.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/recover",
            params={"redirect_to": RESET_URL},
            headers={
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            },
            json={"email": email},
            timeout=15,
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable",
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send recovery email",
        )

    # 이메일 주소가 등록되어 있는지 응답으로 노출하지 않음
    return {"sent": True}


@router.post("/password/reset")
def reset_password(
    body: ResetPasswordRequest,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
):
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    try:
        response = httpx.put(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {credentials.credentials}",
            },
            json={
                "password": body.new_password,
            },
            timeout=15,
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable",
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired recovery link",
        )

    return {"updated": True}
