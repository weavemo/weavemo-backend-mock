# dependencies/auth.py

import logging
from time import perf_counter
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
)
from jose import jwt, JWTError

from config.settings import settings
from db.database import get_supabase


logger = logging.getLogger(__name__)
security = HTTPBearer()


def fetch_user_rows(supabase, auth_uid: str):
    # 읽기 요청만 연결 오류 발생 시 한 번 재시도한다.
    for attempt in range(2):
        try:
            result = (
                supabase.table("users")
                .select(
                    "id, plan, nickname, profile_image_url"
                )
                .eq("auth_uid", auth_uid)
                .limit(1)
                .execute()
            )

            return result.data or []

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
        ):
            if attempt == 1:
                raise

            logger.warning(
                "Auth user lookup connection failed; retrying once"
            )


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    supabase=Depends(get_supabase),
):
    token = creds.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError as error:
        logger.warning(
            "Access token validation failed: %s: %s",
            type(error).__name__,
            str(error),
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    auth_uid = payload.get("sub")
    email = payload.get("email")

    if not auth_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        lookup_started = perf_counter()
        rows = fetch_user_rows(supabase, auth_uid)
        print(
            f"[auth timing] user_lookup="
            f"{(perf_counter() - lookup_started) * 1000:.1f}ms",
            flush=True,
        )
    except Exception:
        logger.exception("Auth user lookup failed")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth backend unavailable",
        )

    if rows:
        user = rows[0]
    else:
        # 생성 요청은 자동 재시도하지 않는다.
        try:
            result = (
                supabase.table("users")
                .insert({
                    "auth_uid": auth_uid,
                    "email": email,
                    "nickname": (
                        email.split("@")[0]
                        if email
                        else "user"
                    ),
                })
                .execute()
            )

            if not result.data:
                raise RuntimeError(
                    "User creation returned no user"
                )

            user = result.data[0]

        except Exception:
            logger.exception("Auth user creation failed")

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User creation failed",
            )

    return {
        "user_id": user["id"],
        "auth_uid": auth_uid,
        "email": email,
        "plan": user.get("plan") or "free",
        "nickname": user.get("nickname"),
        "profile_image_url": user.get("profile_image_url"),
    }
