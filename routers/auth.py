import httpx

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from supabase_auth.errors import AuthApiError

from schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    AuthResponse,
)
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from db.database import get_supabase as get_database_supabase
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


@router.post("/register", response_model=RegisterResponse)
def register(body: RegisterRequest):
    email = body.email.strip()
    nickname = body.nickname.strip()
    notification_timezone = body.notificationTimezone.strip()

    if not email or "@" not in email:
        raise HTTPException(
            status_code=400,
            detail="Invalid email",
        )

    if not nickname:
        raise HTTPException(
            status_code=400,
            detail="Nickname is required",
        )

    if len(body.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters",
        )

    try:
        ZoneInfo(notification_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid notification timezone",
        )

    supabase = get_supabase()

    try:
        res = supabase.auth.sign_up({
            "email": email,
            "password": body.password,
            "options": {
                "data": {
                    "nickname": nickname,
                    "locale": body.locale,
                    "notification_timezone": notification_timezone,
                }
            },
        })
    except AuthApiError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    if not res.user:
        raise HTTPException(
            status_code=400,
            detail="Registration failed",
        )

    # 중복 가입 시 Supabase가 돌려주는 가상 응답으로
    # 기존 사용자의 프로필을 변경하지 않는다.
    identities = getattr(res.user, "identities", None)

    if not res.session and not identities:
        return {
            "confirmationRequired": True,
        }

    # 인증 클라이언트와 분리된 DB 클라이언트를 사용한다.
    database = get_database_supabase()

    try:
        existing_result = (
            database.table("users")
            .select("id")
            .eq("auth_uid", str(res.user.id))
            .limit(1)
            .execute()
        )

        preferences = {
            "nickname": nickname,
            "locale": body.locale,
            "notification_timezone": notification_timezone,
        }

        if existing_result.data:
            profile_result = (
                database.table("users")
                .update(preferences)
                .eq("id", existing_result.data[0]["id"])
                .execute()
            )
        else:
            profile_result = (
                database.table("users")
                .insert({
                    "auth_uid": str(res.user.id),
                    "email": res.user.email or email,
                    **preferences,
                })
                .execute()
            )

        if not profile_result.data:
            raise RuntimeError("Profile write returned no rows")

        profile = profile_result.data[0]

    except Exception as error:
        # 인증 계정은 이미 생성됐을 수 있으므로 삭제하지 않는다.
        print(
            "[auth/register] Profile initialization failed:",
            type(error).__name__,
            flush=True,
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "Account created, but profile setup could not be completed. "
                "Please try logging in before registering again."
            ),
        ) from error

    if not res.session:
        return {
            "confirmationRequired": True,
        }

    return {
        "confirmationRequired": False,
        "user": {
            "id": profile["id"],
            "user_id": profile["id"],
            "auth_uid": str(res.user.id),
            "email": profile.get("email") or email,
            "nickname": profile.get("nickname") or nickname,
            "plan": profile.get("plan") or "free",
            "profile_image_url": profile.get("profile_image_url"),
            "locale": profile.get("locale") or body.locale,
            "notificationTimezone": profile.get("notification_timezone"),
        },
        "token": res.session.access_token,
        "expiresIn": res.session.expires_in,
        "refreshToken": res.session.refresh_token,
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
