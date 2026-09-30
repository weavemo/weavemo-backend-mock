# routers/rewards.py

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()

RewardType = Literal["frame", "skin", "wallpaper"]

EQUIPPED_COLUMNS = {
    "frame": "equipped_frame",
    "skin": "equipped_skin",
    "wallpaper": "equipped_wallpaper",
}


class EquipRequest(BaseModel):
    type: RewardType
    key: str | None = None


def owned_reward_keys(supabase, auth_uid: str) -> set[str]:
    inventory = (
        supabase.table("user_reward_inventory")
        .select("reward_item_id")
        .eq("user_id", auth_uid)
        .execute()
    )

    item_ids = [
        row["reward_item_id"]
        for row in inventory.data or []
    ]

    if not item_ids:
        return set()

    items = (
        supabase.table("reward_items")
        .select("key")
        .in_("id", item_ids)
        .execute()
    )

    return {item["key"] for item in items.data or []}


@router.get("/state")
def get_reward_state(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    owned = owned_reward_keys(supabase, current_user["auth_uid"])

    stats_res = (
        supabase.table("user_stats")
        .select("equipped_frame, equipped_skin, equipped_wallpaper")
        .eq("user_id", current_user["user_id"])
        .limit(1)
        .execute()
    )
    stats = stats_res.data[0] if stats_res.data else {}

    frame = stats.get("equipped_frame")
    skin = stats.get("equipped_skin")
    wallpaper = stats.get("equipped_wallpaper")

    return {
        "owned": sorted(owned),
        "equipped": {
            "frame": frame if frame and f"frame_{frame}" in owned else None,
            "skin": skin if skin in owned else None,
            "wallpaper": wallpaper if wallpaper in owned else None,
        },
    }


@router.put("/equip")
def equip_reward(
    body: EquipRequest,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    owned = owned_reward_keys(supabase, current_user["auth_uid"])

    if body.key is not None:
        key = body.key.strip()

        if not key:
            raise HTTPException(status_code=400, detail="Invalid reward key")

        reward_key = f"frame_{key}" if body.type == "frame" else key

        if reward_key not in owned:
            raise HTTPException(status_code=403, detail="Reward not owned")
    else:
        key = None

    column = EQUIPPED_COLUMNS[body.type]

    result = (
        supabase.table("user_stats")
        .update({column: key})
        .eq("user_id", current_user["user_id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="User stats not found")

    return {"type": body.type, "key": key}
