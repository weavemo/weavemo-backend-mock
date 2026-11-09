import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from db.database import get_supabase
from dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_SAFE_INTEGER = 9007199254740991


class TokenExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tokens: int = Field(strict=True, ge=1, le=1000000)
    expected_points_per_token: int = Field(strict=True, ge=1, le=MAX_SAFE_INTEGER)
    request_id: UUID


def valid_balance(value) -> bool:
    return type(value) is int and 0 <= value <= MAX_SAFE_INTEGER


@router.get("/wallet")
def get_wallet(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        data = supabase.rpc("get_token_exchange_status", {
            "p_user_id": current_user["user_id"],
        }).execute().data
        if not isinstance(data, dict):
            raise ValueError("Invalid wallet response")
        if not valid_balance(data.get("point_balance")) or not valid_balance(data.get("token_balance")):
            raise ValueError("Invalid wallet balances")
        rate = data.get("points_per_token")
        if rate is not None and (not valid_balance(rate) or rate <= 0):
            raise ValueError("Invalid exchange rate")
        if type(data.get("enabled")) is not bool or (data["enabled"] and rate is None):
            raise ValueError("Invalid exchange settings")
        maximum = data.get("max_tokens_per_exchange")
        if type(maximum) is not int or not 1 <= maximum <= 1000000:
            raise ValueError("Invalid exchange limit")
        return data
    except Exception as error:
        logger.exception("Wallet lookup failed")
        raise HTTPException(status_code=503, detail={"reason": "wallet_unavailable"}) from error


@router.post("/exchange")
def exchange_tokens(
    body: TokenExchangeRequest,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        data = supabase.rpc("exchange_points_for_tokens", {
            "p_user_id": current_user["user_id"],
            "p_tokens": body.tokens,
            "p_request_id": str(body.request_id),
            "p_expected_points_per_token": body.expected_points_per_token,
        }).execute().data
    except Exception as error:
        logger.exception("Token exchange failed")
        raise HTTPException(status_code=503, detail={"reason": "exchange_unavailable"}) from error
    if not isinstance(data, dict) or type(data.get("ok")) is not bool:
        raise HTTPException(status_code=503, detail={"reason": "invalid_response"})
    if data["ok"]:
        fields = ("point_balance", "token_balance", "tokens_received", "points_spent", "points_per_token")
        if any(not valid_balance(data.get(key)) for key in fields):
            raise HTTPException(status_code=503, detail={"reason": "invalid_response"})
        if type(data.get("replayed")) is not bool or data["tokens_received"] != body.tokens:
            raise HTTPException(status_code=503, detail={"reason": "invalid_response"})
        if data["points_spent"] != data["tokens_received"] * data["points_per_token"]:
            raise HTTPException(status_code=503, detail={"reason": "invalid_response"})
        if data["points_spent"] <= 0 or data["points_per_token"] <= 0:
            raise HTTPException(status_code=503, detail={"reason": "invalid_response"})
        return data
    statuses = {
        "invalid_request": 422, "user_not_found": 404, "request_conflict": 409,
        "exchange_disabled": 409, "exchange_limit": 422, "insufficient_points": 409,
        "rate_changed": 409, "balance_limit": 409,
    }
    reason = data.get("reason")
    if not isinstance(reason, str) or reason not in statuses:
        raise HTTPException(status_code=503, detail={"reason": "invalid_response"})
    raise HTTPException(status_code=statuses[reason], detail={"reason": reason})


@router.get("/history")
def token_exchange_history(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        rows = supabase.table("token_exchange_requests").select(
            "request_id,tokens,points_spent,points_per_token,created_at"
        ).eq("user_id", current_user["user_id"]).order("created_at", desc=True).limit(20).execute().data
        if not isinstance(rows, list):
            raise ValueError("Invalid exchange history")
        for row in rows:
            if not isinstance(row, dict) or any(
                not valid_balance(row.get(key)) or row[key] <= 0
                for key in ("tokens", "points_spent", "points_per_token")
            ):
                raise ValueError("Invalid exchange history row")
        return {"items": rows}
    except Exception as error:
        logger.exception("Token exchange history lookup failed")
        raise HTTPException(status_code=503, detail={"reason": "history_unavailable"}) from error
