# weavemo-backend-mock/routers/post_media.py

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


def _metadata_state(supabase, storage_path: str) -> str:
    """Return saved/missing/unknown; never assume a failed response means no commit."""
    try:
        result = (
            supabase.table("post_media")
            .select("id")
            .eq("storage_path", storage_path)
            .limit(1)
            .execute()
        )
        if result.data:
            return "saved"
        # Only a successful, unambiguous empty read confirms absence.
        return "missing" if result.data == [] else "unknown"
    except Exception:
        logger.exception("Post image metadata reconciliation failed")
        return "unknown"


def _cleanup_if_missing(supabase, bucket, storage_path: str) -> str:
    """Delete only after confirming no metadata references this exact path."""
    state = _metadata_state(supabase, storage_path)
    if state != "missing":
        return state
    try:
        bucket.remove([storage_path])
        return "removed"
    except Exception:
        logger.exception("Post image orphan cleanup failed: %s", storage_path)
        return "cleanup_failed"


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
        state = _cleanup_if_missing(supabase, bucket, storage_path)
        if state == "saved":
            # The insert committed despite the error response.
            logger.warning("Post image metadata committed despite API error")
            raise HTTPException(status_code=503, detail="Image saved; reload the post")
        if exc.code == "23505":
            raise HTTPException(status_code=409, detail="This post already has an image")
        logger.exception("Post image metadata insert failed; reconciliation=%s", state)
        raise HTTPException(status_code=503, detail="Could not confirm image save; reload the post")
    except Exception:
        state = _cleanup_if_missing(supabase, bucket, storage_path)
        logger.exception("Post image metadata save uncertain; reconciliation=%s", state)
        raise HTTPException(status_code=503, detail="Could not confirm image save; reload the post")

    if not result.data:
        state = _cleanup_if_missing(supabase, bucket, storage_path)
        logger.error("Post image insert returned no data; reconciliation=%s", state)
        raise HTTPException(status_code=503, detail="Could not confirm image save; reload the post")

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
