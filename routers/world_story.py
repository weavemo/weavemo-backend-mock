import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


class FirstMeetingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["completed", "skipped"]


def validate_story(data, require_seen: bool = False) -> dict:
    if not isinstance(data, dict) or type(data.get("seen")) is not bool or type(data.get("version")) is not int:
        raise ValueError("Invalid story response")
    if data["version"] != 1 or (require_seen and not data["seen"]):
        raise ValueError("Invalid story version or state")
    if data["seen"]:
        if data.get("outcome") not in ("completed", "skipped"):
            raise ValueError("Invalid story outcome")
    elif data.get("outcome") is not None:
        raise ValueError("Invalid unread story outcome")
    return {"seen": data["seen"], "outcome": data.get("outcome"), "version": 1}


@router.get("/first-meeting")
def get_first_meeting(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        data = supabase.rpc("get_world_first_meeting", {
            "p_user_id": current_user["user_id"],
        }).execute().data
        return validate_story(data)
    except Exception as error:
        logger.exception("First meeting lookup failed")
        raise HTTPException(status_code=503, detail="Could not load first meeting") from error


@router.post("/first-meeting")
def save_first_meeting(
    body: FirstMeetingRequest,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        data = supabase.rpc("save_world_first_meeting", {
            "p_user_id": current_user["user_id"],
            "p_outcome": body.outcome,
        }).execute().data
        return validate_story(data, require_seen=True)
    except Exception as error:
        logger.exception("First meeting save failed")
        raise HTTPException(status_code=503, detail="Could not save first meeting") from error
