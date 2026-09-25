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

router = APIRouter()


class FrameUpdateRequest(BaseModel):
    frame: Optional[str] = None

class ProfileUpdateRequest(BaseModel):
    nickname: Optional[str] = None


@router.get("/me")
def get_my_profile(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user.get("user_id") or current_user.get("id")

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

    current_metadata = (
        current_user.get("user_metadata")
        or {}
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
