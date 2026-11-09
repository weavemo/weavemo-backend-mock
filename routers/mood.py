# weavemo-backend-mock/routers/mood.py



from __future__ import annotations
from services.analysis_feedback import (
    build_feedback_context,
    verify_feedback_token,
)
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from postgrest.exceptions import APIError
from db.database import get_supabase
from dependencies.auth import get_current_user
from schemas.mood import (
    MoodInput,
    MoodResult,
    MoodAnalysisResponse,
    AnalysisFeedbackLookup,
    AnalysisFeedbackInput,
    AnalysisFeedbackResponse,
)
from services.mood_service import get_mood_analysis

router = APIRouter()


@router.post(
    "/submit",
    response_model=MoodResult,
    status_code=status.HTTP_200_OK,
)
def submit_mood(
    payload: MoodInput,
    supabase=Depends(get_supabase),
    current_user=Depends(get_current_user),
):
    if payload.emotions is None:
        tag_codes = payload.tagIds or []
        emotions = [
            {"code": code, "intensity": None}
            for code in dict.fromkeys(tag_codes)
        ]
    else:
        tag_codes = [emotion.code for emotion in payload.emotions]
        if len(tag_codes) != len(set(tag_codes)):
            raise HTTPException(
                status_code=400,
                detail="Duplicate emotion codes",
            )

        emotions = [
            {"code": emotion.code, "intensity": emotion.intensity}
            for emotion in payload.emotions
        ]

    trigger_types = list(dict.fromkeys(payload.triggerTypes or []))
    other_text = (payload.triggerOtherText or "").strip() or None

    if other_text is not None and "other" not in trigger_types:
        raise HTTPException(
            status_code=400,
            detail="Select the other trigger first",
        )

    today = datetime.now(timezone.utc).date().isoformat()

    try:
        result = supabase.rpc(
            "save_mood_entry_with_reflection",
            {
                "p_user_id": current_user["user_id"],
                "p_main_valence": payload.mainValence,
                "p_energy": payload.energy,
                "p_note": payload.note,
                "p_trigger_type": payload.triggerType,
                "p_emotions": emotions,
                "p_trigger_types": trigger_types,
                "p_other_text": other_text,
                "p_question_key": payload.reflectionQuestionKey,
                "p_answer": payload.reflectionAnswer,
            },
        ).execute()
    except APIError as error:
        if error.code == "P0001" and error.message in {
            "invalid_reflection_question",
            "invalid_reflection_answer",
        }:
            raise HTTPException(status_code=400, detail=error.message) from error
        if error.code == "P0001" and error.message == "invalid_mood_emotion":
            raise HTTPException(
                status_code=400,
                detail="Unknown emotion tag code",
            ) from error
        raise

    return MoodResult(
        moodId=result.data,
        date=today,
        mainValence=payload.mainValence,
        energy=payload.energy,
        triggerType=payload.triggerType,
        note=payload.note,
        tagIds=tag_codes,
    )

# --------------------------------------
# Week 4 — Mood Analysis
# --------------------------------------

@router.get(
    "/analysis",
    response_model=MoodAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
def get_analysis(
    range: str = Query("today", regex="^(today|7d|30d)$"),
    tz_offset_min: int = Header(
        0,
        convert_underscores=False,
        ge=-840,
        le=840,
    ),
    supabase=Depends(get_supabase),
    current_user=Depends(get_current_user),
):
    user_id: int = current_user["user_id"]
    range_key = range.strip().lower()
    is_premium = current_user.get("plan") == "premium"

    # 무료 사용자의 30일 요청은 분석 실행 전에 차단한다.
    if range_key == "30d" and not is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SUBSCRIPTION_REQUIRED",
                "feature": "monthly_analysis",
            },
        )

    try:
        print("[mood/analysis] range=", repr(range))
        print(
            "[mood/analysis] get_mood_analysis file=",
            get_mood_analysis.__code__.co_filename,
        )

        result = get_mood_analysis(
            supabase=supabase,
            user_id=user_id,
            range_key=range_key,
            tz_offset_min=tz_offset_min,
            include_period_insights=is_premium,
        )

        validated = MoodAnalysisResponse.model_validate(result)

        content = jsonable_encoder(
            validated,
            by_alias=True,
            exclude={"feedbackContext"},
        )

        if range_key == "7d" and not is_premium:
            content.pop("periodInsights", None)
            content.pop("period_insights", None)

        # 실제로 반환하는 분석 내용만 식별한다.
        content["feedbackContext"] = build_feedback_context(
            user_id=user_id,
            range_key=range_key,
            tz_offset_min=tz_offset_min,
            content=content,
        )

        # 무료 7일 응답에서 제외한 필드가 기본값으로 붙지 않게 한다.
        return JSONResponse(content=content)
        
    except HTTPException:
        raise

    except ValueError as e:
        print("[mood/analysis] ValueError:", repr(e))

        raise HTTPException(
            status_code=400,
            detail="Invalid range value",
        )

    except Exception as e:
        print(
            "[mood/analysis] Exception:",
            type(e).__name__,
            repr(e),
        )

        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {e}",
        )


# --------------------------------------
# Unique Mood Tag Count
# --------------------------------------

@router.get("/unique-count")
def get_unique_mood_count(
    supabase=Depends(get_supabase),
    current_user=Depends(get_current_user),
):
    user_id: int = current_user["user_id"]

    mood_res = (
        supabase.table("moods")
        .select("id")
        .eq("user_id", user_id)
        .execute()
    )

    mood_ids = [
        row["id"]
        for row in (mood_res.data or [])
    ]

    if not mood_ids:
        return {
            "count": 0,
            "tags": [],
        }

    tag_res = (
        supabase.table("mood_emotion_tags")
        .select("tag_id")
        .in_("mood_id", mood_ids)
        .execute()
    )

    tag_ids = list({
        row["tag_id"]
        for row in (tag_res.data or [])
    })

    if not tag_ids:
        return {
            "count": 0,
            "tags": [],
        }

    emotion_res = (
        supabase.table("emotion_tags")
        .select("code")
        .in_("id", tag_ids)
        .execute()
    )

    target_tags = {
        "anxious",
        "irritated",
        "lethargic",
        "sad",
        "calm",
        "joy",
        "excited",
        "grateful",
    }

    unique_tags = sorted({
        row["code"]
        for row in (emotion_res.data or [])
        if row["code"] in target_tags
    })

    return {
        "count": len(unique_tags),
        "tags": unique_tags,
    }

# 분석 적합도 피드백 조회·저장

def _feedback_claims(token: str, current_user: dict) -> dict:
    claims = verify_feedback_token(
        token,
        int(current_user["user_id"]),
    )

    # 발급 후 구독 상태가 바뀐 경우도 현재 권한을 적용한다.
    if (
        claims["analysis_range"] == "30d"
        and current_user.get("plan") != "premium"
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "SUBSCRIPTION_REQUIRED",
                "feature": "monthly_analysis",
            },
        )

    return claims


@router.post(
    "/analysis/feedback/lookup",
    response_model=AnalysisFeedbackResponse,
)
def lookup_analysis_feedback(
    body: AnalysisFeedbackLookup,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    claims = _feedback_claims(body.token, current_user)

    try:
        result = (
            supabase.table("mood_analysis_helpfulness")
            .select("rating")
            .eq("user_id", int(current_user["user_id"]))
            .eq("report_key", claims["report_key"])
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Could not load analysis feedback",
        ) from error

    return AnalysisFeedbackResponse(
        reportKey=claims["report_key"],
        rating=result.data[0]["rating"] if result.data else None,
    )


@router.put(
    "/analysis/feedback",
    response_model=AnalysisFeedbackResponse,
)
def save_analysis_feedback(
    body: AnalysisFeedbackInput,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    claims = _feedback_claims(body.token, current_user)

    try:
        result = (
            supabase.table("mood_analysis_helpfulness")
            .upsert(
                {
                    "user_id": int(current_user["user_id"]),
                    "report_key": claims["report_key"],
                    "analysis_range": claims["analysis_range"],
                    "analysis_version": claims["analysis_version"],
                    "rating": body.rating,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="user_id,report_key",
            )
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Could not save analysis feedback",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=503,
            detail="Analysis feedback save returned no result",
        )

    return AnalysisFeedbackResponse(
        reportKey=claims["report_key"],
        rating=result.data[0]["rating"],
    )
