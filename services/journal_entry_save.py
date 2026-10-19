from fastapi import HTTPException
from postgrest.exceptions import APIError


def insert_journal_entry(supabase, payload):
    """A request ID belongs to one user and one immutable entry payload."""
    request_id = payload.get("client_request_id")

    def find_existing():
        result = (supabase.table("journal_entries").select("id, content, date, type")
                  .eq("user_id", payload["user_id"])
                  .eq("client_request_id", request_id).limit(1).execute())
        return (result.data or [None])[0]

    def reuse(row):
        if any(str(row.get(key)) != str(payload.get(key))
               for key in ("content", "date", "type")):
            raise HTTPException(status_code=409, detail="Journal request payload changed")
        return {"ok": True, "id": row["id"]}

    if request_id:
        existing = find_existing()
        if existing:
            return reuse(existing)
    try:
        result = supabase.table("journal_entries").insert(payload).execute()
    except APIError as error:
        # The unique index also protects simultaneous retries.
        if request_id and str(getattr(error, "code", "")) == "23505":
            existing = find_existing()
            if existing:
                return reuse(existing)
        raise
    rows = result.data or []
    if not rows:
        raise HTTPException(status_code=503, detail="Journal save was not confirmed")
    return {"ok": True, "id": rows[0]["id"]}
