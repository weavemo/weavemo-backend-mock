# weavemo-backend-mock/routers/onboarding.py

from fastapi import APIRouter, Depends, HTTPException
from db.database import get_supabase
from dependencies.auth import get_current_user
from datetime import datetime, timezone
import logging
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    model_validator,
)


router = APIRouter()


@router.get("/onboarding")
def get_onboarding_status(
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()

    result = (
        supabase.table("users")
        .select("onboarding_completed")
        .eq("id", current_user["user_id"])
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return {
        "completed": result.data[0]["onboarding_completed"],
    }


@router.put("/onboarding/complete")
def complete_onboarding(
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()

    # 여러 번 요청해도 완료 상태는 동일하다.
    result = (
        supabase.table("users")
        .update({"onboarding_completed": True})
        .eq("id", current_user["user_id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return {"completed": True}

# Discover Me — 본인 취향 답변 저장·조회

logger = logging.getLogger(__name__)

DISCOVER_ME_OPTIONS = {
    "activity": {"walk", "breathe", "write"},
    "time": {"morning", "midday", "evening"},
    "rest": {"quiet", "move", "music"},
    "record": {"quick", "detailed", "flexible"},
    "topic": {"stress", "gratitude", "habits"},
    "style": {"gentle", "direct", "varied"},
    "social_activity": {"check_in", "habits", "encourage"},
    "social_frequency": {
        "occasionally",
        "weekly",
        "daily",
        "flexible",
    },
}


class DiscoverMePreferencesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_version: int = Field(
        default=1,
        strict=True,
        ge=1,
        le=1,
    )
    answers: dict[str, StrictStr] = Field(default_factory=dict)
    status: Literal["answered", "skipped"] = "answered"

    @model_validator(mode="after")
    def validate_answers(self):
        for key, value in self.answers.items():
            allowed = DISCOVER_ME_OPTIONS.get(key)

            if allowed is None or value not in allowed:
                raise ValueError("Invalid Discover Me answer")

        if self.status == "skipped" and self.answers:
            raise ValueError("Skipped preferences must have empty answers")

        return self


class DiscoverMePreferencesResponse(BaseModel):
    exists: bool
    question_version: int
    answers: dict[str, str]
    status: Literal["answered", "skipped"] | None
    updated_at: datetime | None


def preferences_response(row: dict) -> DiscoverMePreferencesResponse:
    return DiscoverMePreferencesResponse(
        exists=True,
        question_version=row["question_version"],
        answers=row["answers"],
        status=row["status"],
        updated_at=row["updated_at"],
    )


@router.get(
    "/discover-me",
    response_model=DiscoverMePreferencesResponse,
)
def get_discover_me_preferences(
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        result = (
            supabase.table("user_discover_preferences")
            .select("question_version, answers, status, updated_at")
            .eq("user_id", int(current_user["user_id"]))
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.exception("Discover Me preferences lookup failed")
        raise HTTPException(
            status_code=503,
            detail="Could not load preferences",
        ) from error

    if not result.data:
        return DiscoverMePreferencesResponse(
            exists=False,
            question_version=1,
            answers={},
            status=None,
            updated_at=None,
        )

    return preferences_response(result.data[0])


@router.put(
    "/discover-me",
    response_model=DiscoverMePreferencesResponse,
)
def save_discover_me_preferences(
    body: DiscoverMePreferencesInput,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    try:
        result = (
            supabase.table("user_discover_preferences")
            .upsert(
                {
                    "user_id": int(current_user["user_id"]),
                    "question_version": body.question_version,
                    "answers": body.answers,
                    "status": body.status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="user_id",
            )
            .execute()
        )
    except Exception as error:
        logger.exception("Discover Me preferences save failed")
        raise HTTPException(
            status_code=503,
            detail="Could not save preferences",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=503,
            detail="Preferences save returned no result",
        )

    return preferences_response(result.data[0])
