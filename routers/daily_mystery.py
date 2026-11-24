# routers/daily_mystery.py
"""Private D26 photo missions. All access is scoped to the authenticated user."""
import logging
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from fastapi.responses import Response
from db.database import get_supabase
from dependencies.auth import get_current_user
from services.post_image import MAX_UPLOAD_BYTES, prepare_post_image

router = APIRouter()
logger = logging.getLogger(__name__)
BUCKET = "d26-mystery-private"


def _uid(user):
    return int(user["user_id"])


def _entry(db, uid, entry_id):
    rows = (db.table("d26_mystery_entries").select("id,user_id,storage_path,completed_at")
            .eq("id", entry_id).eq("user_id", uid).limit(1).execute().data or [])
    if not rows:
        raise HTTPException(404, "Mystery not found")
    return rows[0]


@router.post("/today")
def today(tz_offset_min: int = Query(..., ge=-840, le=840),
          user=Depends(get_current_user), db=Depends(get_supabase)):
    try:
        result = db.rpc("d26_assign_today", {"p_user_id": _uid(user),
                      "p_tz_offset_min": tz_offset_min}).execute().data
        if not isinstance(result, dict) or not isinstance(result.get("id"), int):
            raise ValueError("Invalid assignment")
        return result
    except Exception as exc:
        logger.exception("D26 assignment failed")
        raise HTTPException(503, "Mystery unavailable") from exc


@router.post("/{entry_id}/photo")
def submit_photo(entry_id: int, file: UploadFile = File(...),
                 user=Depends(get_current_user), db=Depends(get_supabase)):
    uid = _uid(user)
    entry = _entry(db, uid, entry_id)
    if entry["completed_at"]:
        return {"ok": True, "replayed": True, "tokens": 0}
    processed = prepare_post_image(file.file.read(MAX_UPLOAD_BYTES + 1))
    path = f"{uid}/{entry_id}/{uuid4().hex}.webp"
    bucket = db.storage.from_(BUCKET)
    try:
        bucket.upload(path=path, file=processed, file_options={
            "content-type": "image/webp", "upsert": "false", "cache-control": "0"})
    except Exception as exc:
        logger.exception("D26 upload failed")
        raise HTTPException(503, "Photo upload unavailable") from exc
    try:
        result = db.rpc("d26_complete_photo", {"p_user_id": uid,
                     "p_entry_id": entry_id, "p_storage_path": path}).execute().data
    except Exception as exc:
        # A timeout can occur after commit; never delete a potentially committed image.
        logger.exception("D26 completion uncertain; photo retained for reconciliation")
        raise HTTPException(503, "Completion uncertain; refresh before retrying") from exc
    if not isinstance(result, dict):
        raise HTTPException(503, "Completion response invalid")
    if not result.get("ok"):
        try:
            bucket.remove([path])
        except Exception:
            logger.exception("D26 unused photo cleanup failed")
        raise HTTPException(409, result.get("reason", "Could not complete"))
    if result.get("replayed"):
        try:
            bucket.remove([path])
        except Exception:
            logger.exception("D26 replay photo cleanup failed")
    return result


@router.get("/album")
def album(user=Depends(get_current_user), db=Depends(get_supabase)):
    try:
        rows = (db.table("d26_mystery_entries")
                .select("id,local_date,prompt_id,completed_at,reflection_note")
                .eq("user_id", _uid(user)).not_.is_("completed_at", "null")
                .order("completed_at", desc=True).limit(100).execute().data)
        prompts = (db.table("d26_mystery_prompts")
                   .select("id,title_ko,title_en,reflection_ko,reflection_en")
                   .execute().data or [])
        lookup = {int(p["id"]): p for p in prompts}
        awards = (db.table("d26_memory_awards")
                  .select("milestone,reward_key,granted_at")
                  .eq("user_id", _uid(user)).order("milestone").execute().data or [])
        items = [{**row, "prompt": lookup.get(row["prompt_id"])} for row in (rows or [])]
        count_result = (db.table("d26_mystery_entries").select("id", count="exact", head=True)
                        .eq("user_id", _uid(user)).not_.is_("completed_at", "null").execute())
        return {"items": items, "awards": awards, "count": count_result.count or 0}
    except Exception as exc:
        logger.exception("D26 album lookup failed")
        raise HTTPException(503, "Album unavailable") from exc


@router.get("/{entry_id}/photo")
def get_photo(entry_id: int, user=Depends(get_current_user), db=Depends(get_supabase)):
    entry = _entry(db, _uid(user), entry_id)
    if not entry["completed_at"] or not entry["storage_path"]:
        raise HTTPException(404, "Photo not found")
    try:
        content = db.storage.from_(BUCKET).download(entry["storage_path"])
    except Exception as exc:
        logger.exception("D26 photo read failed")
        raise HTTPException(503, "Photo unavailable") from exc
    return Response(content=content, media_type="image/webp", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


class ReflectionUpdate(BaseModel):
    note: str = Field(max_length=500)


@router.patch("/{entry_id}/reflection")
def update_reflection(entry_id: int, payload: ReflectionUpdate,
                      user=Depends(get_current_user), db=Depends(get_supabase)):
    uid = _uid(user)
    entry = _entry(db, uid, entry_id)
    if not entry["completed_at"]:
        raise HTTPException(409, "Complete the photo mission first")
    try:
        db.table("d26_mystery_entries").update({
            "reflection_note": payload.note.strip()
        }).eq("id", entry_id).eq("user_id", uid).execute()
        return {"ok": True}
    except Exception as exc:
        logger.exception("D26 reflection save failed")
        raise HTTPException(503, "Could not save reflection") from exc
