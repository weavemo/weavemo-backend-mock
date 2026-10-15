from fastapi import APIRouter, Depends
from dependencies.auth import get_current_user

router = APIRouter(prefix="/analysis-access", tags=["analysis-access"])


@router.get("")
def get_analysis_access(current_user=Depends(get_current_user)):
    # get_current_user reads the current users.plan from the database.
    return {"premium": current_user.get("plan") == "premium"}
