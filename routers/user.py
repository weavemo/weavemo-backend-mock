# routers/user.py

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from pydantic import BaseModel
from dependencies.auth import get_current_user
from db.database import get_supabase
from typing import Optional
from pathlib import Path
from uuid import uuid4
import httpx
from config.settings import settings
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer()

router = APIRouter()


class FrameUpdateRequest(BaseModel):
    frame: Optional[str] = None

class ProfileUpdateRequest(BaseModel):
    nickname: Optional[str] = None


@router.get("/me")
def get_my_profile(
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    try:
        auth_response = supabase.auth.get_user(
            credentials.credentials
        )
        auth_user = auth_response.user
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not verify account email",
        )

    if not auth_user or auth_user.id != current_user["auth_uid"]:
        raise HTTPException(
            status_code=401,
            detail="Account mismatch",
        )

    verified_email = auth_user.email

    if (
        verified_email
        and verified_email != current_user.get("email")
    ):
        supabase.table("users").update({
            "email": verified_email
        }).eq("id", user_id).execute()

    stats_res = (
        supabase.table("user_stats")
        .select("level, xp, equipped_frame")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    stats = stats_res.data[0] if stats_res.data else {}

    return {
        "user": {
            **current_user,
            "email": verified_email or current_user.get("email"),
            "level": stats.get("level", 1),
            "xp": stats.get("xp", 0),
            "equipped_frame": stats.get("equipped_frame"),
        }
    }

@router.get("/equipped")
def get_equipped(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user.get("user_id") or current_user.get("id")

    res = (
        supabase.table("user_stats")
        .select("equipped_frame")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    data = res.data[0] if res.data else {}

    return {
        "frame": data.get("equipped_frame"),
        "skin": None,   # 나중 확장
        "badge": None,  # 나중 확장
    }


@router.patch("/frame")
def update_frame(
    body: FrameUpdateRequest,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    supabase.table("user_stats").update({
        "equipped_frame": body.frame
    }).eq("user_id", user_id).execute()

    return {"equipped_frame": body.frame}

@router.put("/profile")
def update_profile(
    body: ProfileUpdateRequest,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()

    user_id = current_user.get(
        "user_id"
    )

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid user",
        )

    nickname = (
        body.nickname.strip()
        if body.nickname
        else None
    )

    if not nickname:
        raise HTTPException(
            status_code=400,
            detail="Nickname is required",
        )

    if len(nickname) > 30:
        raise HTTPException(
            status_code=400,
            detail="Nickname is too long",
        )

    result = (
        supabase.table("users")
        .update({
            "nickname": nickname,
        })
        .eq("id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    updated_user = result.data[0]

    return {
        "id": updated_user.get(
            "id"
        ),
        "email": updated_user.get(
            "email",
            current_user.get("email"),
        ),
        "nickname": updated_user.get(
            "nickname"
        ),
        "profile_image_url":
            updated_user.get(
                "profile_image_url"
            ),
    }

@router.post("/profile/image")
async def upload_profile_image(
    request: Request,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()

    user_id = (
        current_user.get("user_id")
        or current_user.get("id")
    )

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid user",
        )

    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    extension = allowed_types.get(
        file.content_type or ""
    )

    if not extension:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, PNG and WEBP "
                "images are allowed"
            ),
        )

    contents = await file.read()

    max_size = 5 * 1024 * 1024

    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail="Image must be 5MB or smaller",
        )

    upload_directory = Path(
        "uploads/profiles"
    )

    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = (
        f"{user_id}_{uuid4().hex}"
        f"{extension}"
    )

    file_path = (
        upload_directory / filename
    )

    file_path.write_bytes(contents)

    image_url = str(
        request.url_for(
            "uploads",
            path=f"profiles/{filename}",
        )
    )

    result = (
        supabase.table("users")
        .update({
            "profile_image_url":
                image_url,
        })
        .eq("id", user_id)
        .execute()
    )
    
    if not result.data:
        if file_path.exists():
            file_path.unlink()
    
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    return {
        "profile_image_url":
            image_url,
    }

class EmailChangeRequest(BaseModel):
    email: str
    current_password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


def verify_current_password(
    email: str,
    password: str,
    auth_uid: str,
):
    try:
        response = httpx.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token",
            params={"grant_type": "password"},
            headers={
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            },
            json={
                "email": email,
                "password": password,
            },
            timeout=15,
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect",
        )

    signed_in_user = response.json().get("user") or {}
    if signed_in_user.get("id") != auth_uid:
        raise HTTPException(
            status_code=401,
            detail="Account mismatch",
        )


def update_auth_user(token: str, changes: dict, redirect_to: str | None = None):
    try:
        response = httpx.put(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user",
            params={"redirect_to": redirect_to} if redirect_to else None,
            headers={
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {token}",
            },
            json=changes,
            timeout=15,
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=400,
            detail="Account update failed",
        )

    return response.json()


@router.post("/profile/email")
def change_email(
    body: EmailChangeRequest,
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
):
    new_email = body.email.strip().lower()
    old_email = current_user.get("email")

    if not new_email or "@" not in new_email:
        raise HTTPException(
            status_code=400,
            detail="Enter a valid email address",
        )

    if new_email == old_email:
        raise HTTPException(
            status_code=400,
            detail="Email is unchanged",
        )

    verify_current_password(
        old_email,
        body.current_password,
        current_user["auth_uid"],
    )

    update_auth_user(
        credentials.credentials,
        {"email": new_email},
        redirect_to="http://www.localhost:5173/login",
    )

    # 여기서 users.email을 변경하지 않는다.
    # 이메일 확인이 완료되기 전까지는 이전 이메일이 유효하다.
    return {"confirmation_required": True}


@router.post("/profile/password")
def change_password(
    body: PasswordChangeRequest,
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
):
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters",
        )

    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=400,
            detail="Choose a different password",
        )

    verify_current_password(
        current_user["email"],
        body.current_password,
        current_user["auth_uid"],
    )

    update_auth_user(
        credentials.credentials,
        {"password": body.new_password},
    )

    return {"updated": True}
