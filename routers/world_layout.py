import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)
ItemKey = Literal["companion", "cozy_blanket", "warming_lamp"]


class WorldPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    x: float = Field(strict=True, ge=0, le=1)
    y: float = Field(strict=True, ge=0, le=1)
    layer: int = Field(strict=True, ge=0, le=20)


class WorldLayoutInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(strict=True, ge=0, le=9007199254740991)
    placements: dict[ItemKey, WorldPosition] = Field(min_length=1, max_length=3)


class WorldLayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: Literal[True]
    revision: int = Field(strict=True, ge=0, le=9007199254740991)
    placements: dict[ItemKey, WorldPosition] = Field(min_length=1, max_length=3)


def call_layout(name: str, params: dict) -> WorldLayoutResponse:
    try:
        data = get_supabase().rpc(name, params).execute().data
    except Exception as error:
        logger.exception("World layout operation failed")
        raise HTTPException(status_code=503, detail="World layout unavailable") from error
    if isinstance(data, dict) and data.get("ok") is False:
        reason = data.get("reason")
        status = {
            "user_not_found": 404,
            "invalid_request": 422,
            "world_not_initialized": 409,
            "equipment_not_installed": 409,
            "revision_conflict": 409,
            "revision_limit": 409,
        }.get(reason, 503) if isinstance(reason, str) else 503
        raise HTTPException(status_code=status, detail=data)
    try:
        result = WorldLayoutResponse.model_validate(data)
        if "companion" not in result.placements:
            raise ValueError("Missing companion position")
        return result
    except Exception as error:
        logger.exception("Invalid world layout response")
        raise HTTPException(status_code=503, detail="Invalid world layout response") from error


@router.get("/layout", response_model=WorldLayoutResponse)
def get_world_layout(current_user=Depends(get_current_user)):
    return call_layout("get_my_world_layout", {"p_user_id": current_user["user_id"]})


@router.put("/layout", response_model=WorldLayoutResponse)
def save_world_layout(body: WorldLayoutInput, current_user=Depends(get_current_user)):
    if "companion" not in body.placements:
        raise HTTPException(status_code=422, detail="Companion position is required")
    return call_layout("save_my_world_layout", {
        "p_user_id": current_user["user_id"],
        "p_expected_revision": body.expected_revision,
        "p_placements": {key: value.model_dump() for key, value in body.placements.items()},
    })
