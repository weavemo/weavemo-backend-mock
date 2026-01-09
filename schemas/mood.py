# weavemo-backend/schemas/mood.py
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


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

# -------------------------
# Analysis enums
# -------------------------
class SummaryLabel(str, Enum):
    LOW_VALENCE_LOW_ENERGY = "LOW_VALENCE_LOW_ENERGY"
    LOW_VALENCE_HIGH_ENERGY = "LOW_VALENCE_HIGH_ENERGY"
    HIGH_VALENCE_LOW_ENERGY = "HIGH_VALENCE_LOW_ENERGY"
    HIGH_VALENCE_HIGH_ENERGY = "HIGH_VALENCE_HIGH_ENERGY"
    NEUTRAL = "NEUTRAL"


# -------------------------
# Analysis sub models
# -------------------------
class MoodAnalysisSummary(BaseModel):
    mainValence: int
    energy: int
    label: SummaryLabel
    hasNote: bool


class MoodAnalysisPoint(BaseModel):
    date: str
    mainValence: int
    energy: int
    recordedAt: Optional[str] = None


class MoodTagSummaryItem(BaseModel):
    code: str
    count: int

class MoodAnalysisMetrics(BaseModel):
    avg_valence: float
    avg_energy: float
    valence_trend: str   # up | down | flat
    energy_trend: str    # up | down | flat
    energy_volatility: str  # low | medium | high
    positive_ratio: float
    dominant_tags: List[str]


class TodayMoodInfo(BaseModel):
    moodId: int
    note: Optional[str]
    triggerType: Optional[str]


# -------------------------
# Analysis response
# -------------------------
class MoodAnalysisResponse(BaseModel):
    range: str
    summary: MoodAnalysisSummary
    points: List[MoodAnalysisPoint]
    tagsSummary: List[MoodTagSummaryItem]
    metrics: MoodAnalysisMetrics
    todayMood: Optional[TodayMoodInfo] = None
