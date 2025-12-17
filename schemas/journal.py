from pydantic import BaseModel

class JournalCreate(BaseModel):
    content: str
