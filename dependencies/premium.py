# weavemo-backend-mock/dependencies/premium.py
from fastapi import Depends, HTTPException, status
from dependencies.auth import get_current_user


def require_premium(current_user=Depends(get_current_user)):
    if current_user["plan"] != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium required",
        )
    return current_user
