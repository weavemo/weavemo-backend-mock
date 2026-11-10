import logging

from fastapi import APIRouter, Depends, HTTPException

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/inventory")
def get_companion_inventory(current_user=Depends(get_current_user)):
    try:
        data = get_supabase().rpc(
            "get_my_companion_inventory",
            {"p_user_id": current_user["user_id"]},
        ).execute().data
        if not isinstance(data, dict):
            raise ValueError("Invalid inventory response")
        if data.get("ok") is not True:
            reason = data.get("reason")
            if reason in ("user_not_found", "world_not_initialized"):
                raise HTTPException(
                    status_code=404 if reason == "user_not_found" else 409,
                    detail=data,
                )
            raise ValueError("Invalid inventory result")
        if data.get("stage") not in ("egg", "hatched", "grown") or not isinstance(data.get("items"), list):
            raise ValueError("Invalid inventory contents")
        keys = set()
        for item in data["items"]:
            if not isinstance(item, dict):
                raise ValueError("Invalid inventory item")
            key = item.get("key")
            if not isinstance(key, str) or not key or key in keys:
                raise ValueError("Invalid inventory key")
            keys.add(key)
            if any(not isinstance(item.get(field), str) for field in ("name_ko", "name_en")):
                raise ValueError("Invalid inventory name")
            for field in ("unused_quantity", "stored_quantity", "installed_quantity", "available_quantity"):
                value = item.get(field)
                if type(value) is not int or not 0 <= value <= 9007199254740991:
                    raise ValueError("Invalid inventory quantity")
            if item["available_quantity"] != item["unused_quantity"] + item["stored_quantity"]:
                raise ValueError("Invalid available quantity")
        return data
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Companion inventory lookup failed")
        raise HTTPException(status_code=503, detail="Inventory unavailable") from error
