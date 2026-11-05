import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


class PurchaseRequest(BaseModel):
    item_key: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    request_id: UUID
    quantity: int = Field(default=1, strict=True, ge=1, le=99)

class BlanketInstallRequest(BaseModel):
    slot_number: int = Field(strict=True, ge=1, le=10)
    request_id: UUID

@router.get("/items")
def get_shop_items(
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    try:
        items = (
            supabase.table("companion_shop_items")
            .select(
                "key, name_ko, name_en, "
                "care_action, token_price, sort_order"
            )
            .eq("is_enabled", True)
            .order("sort_order")
            .order("key")
            .execute()
            .data
        ) or []

        inventory = (
            supabase.table("user_companion_inventory")
            .select("item_key, quantity")
            .eq("user_id", user_id)
            .execute()
            .data
        ) or []

        wallets = (
            supabase.table("user_point_wallets")
            .select("balance")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        ) or []

    except APIError as error:
        logger.exception("Companion shop load failed")
        raise HTTPException(
            status_code=503,
            detail="Shop unavailable",
        ) from error

    owned = {
        row["item_key"]: row["quantity"]
        for row in inventory
    }

    return {
        "point_balance": wallets[0]["balance"] if wallets else 0,
        "items": [
            {
                **item,
                "owned_quantity": owned.get(item["key"], 0),
            }
            for item in items
        ],
    }


@router.post("/purchase")
def purchase_item(
    body: PurchaseRequest,
    current_user=Depends(get_current_user),
):
    try:
        result = (
            get_supabase()
            .rpc(
                "buy_companion_items",
                {
                    "p_user_id": current_user["user_id"],
                    "p_item_key": body.item_key,
                    "p_quantity": body.quantity,
                    "p_request_id": str(body.request_id),
                },
            )
            .execute()
        )
    except APIError as error:
        logger.exception("Companion shop purchase failed")
        raise HTTPException(
            status_code=503,
            detail="Purchase unavailable",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid purchase response",
        )

    if data.get("ok") is True:
        return data

    reason = data.get("reason")

    status_codes = {
        "invalid_request": 422,
        "user_not_found": 404,
        "world_not_initialized": 409,
        "item_not_found": 404,
        "item_unavailable": 409,
        "request_conflict": 409,
        "insufficient_tokens": 409,
        "already_owned": 409,
        "quantity_limit": 422,
    }

    status_code = (
        status_codes.get(reason, 503)
        if isinstance(reason, str)
        else 503
    )

    raise HTTPException(
        status_code=status_code,
        detail=data,
    )

def call_install_rpc(name: str, params: dict) -> dict:
    try:
        result = get_supabase().rpc(name, params).execute()
    except APIError as error:
        logger.exception("Companion installation failed: %s", name)
        raise HTTPException(
            status_code=503,
            detail="Installation unavailable",
        ) from error

    data = result.data

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid installation response",
        )

    if data.get("ok") is True:
        return data

    reason = data.get("reason")

    status_codes = {
        "invalid_request": 422,
        "invalid_slot": 422,
        "user_not_found": 404,
        "world_not_initialized": 409,
        "request_conflict": 409,
        "lamp_already_installed": 409,
        "blanket_still_new": 409,
        "item_not_owned": 409,
    }

    status_code = (
        status_codes.get(reason, 503)
        if isinstance(reason, str)
        else 503
    )

    raise HTTPException(
        status_code=status_code,
        detail=data,
    )


@router.post("/blankets/install")
def install_blanket(
    body: BlanketInstallRequest,
    current_user=Depends(get_current_user),
):
    return call_install_rpc(
        "install_companion_blanket",
        {
            "p_user_id": current_user["user_id"],
            "p_slot_number": body.slot_number,
            "p_request_id": str(body.request_id),
        },
    )


@router.post("/lamp/install")
def install_lamp(
    current_user=Depends(get_current_user),
):
    return call_install_rpc(
        "install_companion_lamp",
        {
            "p_user_id": current_user["user_id"],
        },
    )


@router.get("/thermal")
def get_thermal_status(
    current_user=Depends(get_current_user),
):
    return call_install_rpc(
        "get_companion_thermal_status",
        {
            "p_user_id": current_user["user_id"],
        },
    )
