# weavemo-backend/schemas/mood.py

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MoodInput(BaseModel):
    mainValence: int = Field(
        ...,
        ge=-2,
        le=2,
    )
    energy: int = Field(
        ...,
        ge=1,
        le=5,
    )

    tagIds: Optional[List[str]] = None
    triggerType: Optional[str] = None
    note: Optional[str] = Field(
        default=None,
        max_length=200,
    )


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
    LOW_VALENCE_LOW_ENERGY = (
        "LOW_VALENCE_LOW_ENERGY"
    )
    LOW_VALENCE_HIGH_ENERGY = (
        "LOW_VALENCE_HIGH_ENERGY"
    )
    HIGH_VALENCE_LOW_ENERGY = (
        "HIGH_VALENCE_LOW_ENERGY"
    )
    HIGH_VALENCE_HIGH_ENERGY = (
        "HIGH_VALENCE_HIGH_ENERGY"
    )
    NEUTRAL = "NEUTRAL"


# -------------------------
# Basic analysis models
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

    valence_trend: str
    energy_trend: str

    energy_volatility: str

    positive_ratio: float
    dominant_tags: List[str]


# -------------------------
# Today mood details
# -------------------------

class TodayMoodInfo(BaseModel):
    moodId: int
    note: Optional[str]
    triggerType: Optional[str]


class TodayMoodNote(BaseModel):
    moodId: int
    recordedAt: Optional[str] = None
    note: str
    triggerType: Optional[str] = None


# -------------------------
# Professional period analysis
# -------------------------

class MoodTriggerSummaryItem(BaseModel):
    trigger_type: str
    count: int


class MoodDailyInsight(BaseModel):
    date: str

    avg_valence: float
    avg_energy: float

    checkin_count: int
    note_count: int

    positive_ratio: float


class MoodWeeklyInsight(BaseModel):
    week_start: str
    week_end: str

    avg_valence: float
    avg_energy: float

    positive_ratio: float

    checkin_count: int
    note_count: int
    active_days: int


class MoodPeriodComparison(BaseModel):
    previous_available: bool = False

    avg_valence_delta: float = 0.0
    avg_energy_delta: float = 0.0
    positive_ratio_delta: float = 0.0

    checkin_count_delta: int = 0
    active_days_delta: int = 0


class MoodPeriodInsights(BaseModel):
    checkin_count: int = 0
    active_days: int = 0
    note_count: int = 0

    consistency_score: float = 0.0

    strongest_day: Optional[str] = None
    difficult_day: Optional[str] = None
    most_variable_day: Optional[str] = None

    dominant_trigger: Optional[str] = None

    trigger_summary: List[
        MoodTriggerSummaryItem
    ] = Field(
        default_factory=list
    )

    daily_insights: List[
        MoodDailyInsight
    ] = Field(
        default_factory=list
    )

    weekly_insights: List[
        MoodWeeklyInsight
    ] = Field(
        default_factory=list
    )

    comparison: MoodPeriodComparison = Field(
        default_factory=MoodPeriodComparison
    )

    insight_codes: List[str] = Field(
        default_factory=list
    )


# -------------------------
# Analysis response
# -------------------------

class MoodAnalysisResponse(BaseModel):
    range: str

    summary: MoodAnalysisSummary

    points: List[
        MoodAnalysisPoint
    ]

    tagsSummary: List[
        MoodTagSummaryItem
    ]

    metrics: MoodAnalysisMetrics

    todayMood: Optional[
        TodayMoodInfo
    ] = None

    todayMoodNotes: List[
        TodayMoodNote
    ] = Field(
        default_factory=list
    )

    periodInsights: Optional[
        MoodPeriodInsights
    ] = None
