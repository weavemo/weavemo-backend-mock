from fastapi import APIRouter, Depends
from datetime import date
from dependencies.auth import get_current_user
from db.database import get_supabase
from schemas.journal import JournalCreate

router = APIRouter()

@router.post("")
def create_journal(
    body: JournalCreate,
    current_user=Depends(get_current_user),
):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    res = supabase.table("journals").insert({
        "user_id": user_id,
        "content": body.content,
        "created_at": "now()",
    }).execute()

    return {"ok": True}
