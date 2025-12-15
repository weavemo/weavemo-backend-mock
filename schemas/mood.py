# weavemo-backend/schemas/mood.py
from typing import List, Optional
from pydantic import BaseModel, Field


class MoodInput(BaseModel):
    mainValence: int = Field(..., ge=-2, le=2)
    energy: int = Field(..., ge=1, le=5)

    tagIds: Optional[List[str]] = None
    triggerType: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=200)


class MoodResult(BaseModel):
    moodId: int
    date: str

    mainValence: int
    energy: int

    triggerType: Optional[str]
    note: Optional[str]
    tagIds: List[str]
