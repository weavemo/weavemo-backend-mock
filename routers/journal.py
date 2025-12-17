# routers/journal.py
from fastapi import APIRouter, Depends, HTTPException
from dependencies.auth import get_current_user
from db.database import get_supabase
from schemas.journal import JournalCreate

router = APIRouter()


# CREATE
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
    }).execute()

    return res.data[0]


# LIST
@router.get("")
def list_journals(current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    res = (
        supabase.table("journals")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {"items": res.data}


# DETAIL
@router.get("/{journal_id}")
def get_journal(journal_id: int, current_user=Depends(get_current_user)):
    supabase = get_supabase()
    user_id = current_user["user_id"]

    res = (
        supabase.table("journals")
        .select("*")
        .eq("id", journal_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not res.data:
        raise HTTPException(status_code=404, detail="Journal not found")

    return res.data[0]
