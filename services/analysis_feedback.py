# services/analysis_feedback.py

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from fastapi import HTTPException

from config.settings import settings


ANALYSIS_VERSION = 2
TOKEN_AUDIENCE = "weavemo-analysis-feedback"
TOKEN_ISSUER = "weavemo-backend"


def _signing_key() -> str:
    # 로그인 토큰과 구분되는 피드백 전용 서명 키를 파생한다.
    return hmac.new(
        settings.SUPABASE_JWT_SECRET.encode("utf-8"),
        b"weavemo:analysis-feedback:v1",
        hashlib.sha256,
    ).hexdigest()


def build_feedback_context(
    user_id: int,
    range_key: str,
    tz_offset_min: int,
    content: dict,
) -> dict | None:
    if not content.get("points"):
        return None

    now = datetime.now(timezone.utc)
    local_date = (
        now + timedelta(minutes=tz_offset_min)
    ).date().isoformat()

    identity = {
        "user_id": str(user_id),
        "range": range_key,
        "local_date": local_date,
        "tz_offset_min": tz_offset_min,
        "analysis_version": ANALYSIS_VERSION,
        "content": content,
    }

    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    # 원문을 추측·대입하기 어렵도록 단순 해시 대신 HMAC을 사용한다.
    report_key = hmac.new(
        _signing_key().encode("utf-8"),
        encoded,
        hashlib.sha256,
    ).hexdigest()

    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": TOKEN_AUDIENCE,
            "iss": TOKEN_ISSUER,
            "purpose": "analysis_feedback",
            "report_key": report_key,
            "analysis_range": range_key,
            "analysis_version": ANALYSIS_VERSION,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=24)).timestamp()),
        },
        _signing_key(),
        algorithm="HS256",
    )

    return {
        "reportKey": report_key,
        "analysisVersion": ANALYSIS_VERSION,
        "token": token,
    }


def verify_feedback_token(token: str, user_id: int) -> dict:
    try:
        payload = jwt.decode(
            token,
            _signing_key(),
            algorithms=["HS256"],
            audience=TOKEN_AUDIENCE,
            issuer=TOKEN_ISSUER,
            options={
                "require_exp": True,
                "require_sub": True,
                "require_aud": True,
                "require_iss": True,
            },
        )
    except JWTError as error:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired analysis feedback token",
        ) from error

    report_key = payload.get("report_key")

    if (
        payload.get("sub") != str(user_id)
        or payload.get("purpose") != "analysis_feedback"
        or payload.get("analysis_range") not in {"today", "7d", "30d"}
        or type(payload.get("analysis_version")) is not int
        or payload["analysis_version"] != ANALYSIS_VERSION
        or not isinstance(report_key, str)
        or len(report_key) != 64
        or any(char not in "0123456789abcdef" for char in report_key)
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid analysis feedback token",
        )

    return payload
