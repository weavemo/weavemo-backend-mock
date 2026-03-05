# weavemo-backend-mock/dependencies/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from httpx import ReadError

from config.settings import settings
from db.database import get_supabase

security = HTTPBearer()


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
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    auth_uid = payload.get("sub")
    email = payload.get("email")

    if not auth_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # 1️⃣ users 테이블에서 auth_uid로 조회
    try:
        res = (
            supabase.table("users")
            .select("id, plan")
            .eq("auth_uid", auth_uid)
            .limit(1)
            .execute()
        )
    except ReadError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth backend temporarily unavailable",
        )

    rows = res.data or []

    # 2️⃣ 없으면 자동 생성 (Week 3 기준 허용)
    if rows:
        user_id = rows[0]["id"]
        plan = rows[0].get("plan")
    else:
        created = (
            supabase.table("users")
            .insert({
                "auth_uid": auth_uid,
                "email": email,
                "nickname": email.split("@")[0] if email else "user",
            })
            .execute()
        )
        user_id = created.data[0]["id"]
        plan = "free"

    # 3️⃣ 내부 user 객체 반환 (BIGINT id!)
    return {
        "user_id": user_id,   # ✅ DB에서 쓰는 ID
        "auth_uid": auth_uid, # 참고용
        "email": email,
        "plan": plan,
    }
