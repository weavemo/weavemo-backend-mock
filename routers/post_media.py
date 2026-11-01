# C:\Users\myh03\project_weavemo\weavemo-backend-mock\routers\post_media.py

import logging
from fastapi.responses import Response
from dependencies.auth import get_current_user
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

    #     # 파일 전체를 읽지 않고 최대 허용 크기보다 1바이트까지만 읽는다.
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
             # 동시 업로드로 충돌하면 이번 요청이 올린 사진만 삭제한다.
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
        # DB에는 저장됐지만 응답만 유실됐을 수 있으므로
        # 이 단계에서는 Storage의 사진을 삭제하지 않는다.
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
# 게시물 공개 범위와 차단 관계를 확인한 후 사진을 반환한다.
@router.get("/{post_id}/media")
def get_post_image(
    post_id: int,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    require_post_access(
        supabase,
        post_id,
        current_user,
    )

    result = (
        supabase.table("post_media")
        .select("storage_path, mime_type")
        .eq("post_id", post_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Image not found",
        )

    media = result.data[0]

    try:
        image_bytes = (
            supabase.storage.from_(BUCKET)
            .download(media["storage_path"])
        )
    except Exception:
        logger.exception("Post image download failed")
        raise HTTPException(
            status_code=503,
            detail="Image temporarily unavailable",
        )

    return Response(
        content=image_bytes,
        media_type=media["mime_type"],
        headers={
            # 권한이 바뀐 뒤에도 브라우저 캐시로 재사용되지 않게 한다.
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
