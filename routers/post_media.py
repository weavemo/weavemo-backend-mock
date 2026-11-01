# C:\Users\myh03\project_weavemo\weavemo-backend-mock\routers\post_media.py

import logging
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from postgrest.exceptions import APIError

from db.database import get_supabase
from dependencies.premium import require_premium
from services.post_access import require_post_access
from services.post_image import (
    MAX_UPLOAD_BYTES,
    prepare_post_image,
)


router = APIRouter()
logger = logging.getLogger(__name__)
BUCKET = "post-media"


@router.post("/{post_id}/media", status_code=201)
def upload_post_image(
    post_id: int,
    file: UploadFile = File(...),
    current_user=Depends(require_premium),
    supabase=Depends(get_supabase),
):
    post = require_post_access(
        supabase,
        post_id,
        current_user,
    )

    if int(post["user_id"]) != int(current_user["user_id"]):
        raise HTTPException(
            status_code=403,
            detail="Only the author can upload an image",
        )

    existing = (
        supabase.table("post_media")
        .select("id")
        .eq("post_id", post_id)
        .limit(1)
        .execute()
    )

    if existing.data:
        raise HTTPException(
            status_code=409,
            detail="This post already has an image",
        )

    # 全量を読み込む前に、読み取り量を制限する。
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    processed = prepare_post_image(raw)

    storage_path = f"{post_id}/{uuid4().hex}.webp"
    bucket = supabase.storage.from_(BUCKET)

    try:
        bucket.upload(
            path=storage_path,
            file=processed,
            file_options={
                "content-type": "image/webp",
                "upsert": "false",
                "cache-control": "0",
            },
        )
    except Exception:
        logger.exception("Post image storage upload failed")
        raise HTTPException(
            status_code=503,
            detail="Image upload failed",
        )

    try:
        result = (
            supabase.table("post_media")
            .insert({
                "post_id": post_id,
                "storage_path": storage_path,
                "mime_type": "image/webp",
                "size_bytes": len(processed),
            })
            .execute()
        )
    except APIError as exc:
        if exc.code == "23505":
            # 同時アップロードで競合した、このリクエストの写真だけを削除する。
            try:
                bucket.remove([storage_path])
            except Exception:
                logger.exception("Duplicate image cleanup failed")

            raise HTTPException(
                status_code=409,
                detail="This post already has an image",
            )

        logger.exception("Post image metadata insert failed")
        raise HTTPException(
            status_code=503,
            detail="Could not save image information",
        )
    except Exception:
        # DB保存済みで応答だけ失われた可能性があるため、
        # この時点ではStorageの写真を削除しない。
        logger.exception("Post image metadata save uncertain")
        raise HTTPException(
            status_code=503,
            detail="Could not confirm image save; reload the post",
        )

    if not result.data:
        raise HTTPException(
            status_code=503,
            detail="Could not confirm image save; reload the post",
        )

    media = result.data[0]

    return {
        "id": str(media["id"]),
        "postId": str(post_id),
        "mimeType": "image/webp",
        "sizeBytes": len(processed),
    }
