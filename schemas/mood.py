# weavemo-backend/schemas/mood.py

from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field


MoodTriggerCode = Literal[
    "people", "work", "health", "money", "weather", "other",
    "study", "sleep", "family", "exercise", "rest", "life_change",
]


class MoodEmotionInput(BaseModel):
    code: str = Field(min_length=1)
    intensity: int = Field(strict=True, ge=1, le=5)

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
    emotions: Optional[List[MoodEmotionInput]] = None
    triggerTypes: Optional[List[MoodTriggerCode]] = None
    triggerOtherText: Optional[str] = Field(default=None, max_length=200)
    reflectionQuestionKey: Optional[str] = Field(default=None, max_length=64)
    reflectionAnswer: Optional[str] = Field(default=None, max_length=200)
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

    advice_codes: List[str] = Field(
        default_factory=list
    )


# 감정 구성과 강도
class MoodEmotionDetail(BaseModel):
    code: str
    count: int
    intensity_count: int
    average_intensity: Optional[float] = None


# 같은 기록에서 함께 선택한 감정
class MoodEmotionPair(BaseModel):
    codes: List[str]
    count: int


# 선택한 영향 요인과 함께 기록된 상태
class MoodTriggerDetail(BaseModel):
    code: str
    count: int
    avg_valence: float
    avg_energy: float


# 현재 분석 범위의 기록 상태
class MoodObservation(BaseModel):
    checkin_count: int
    active_days: int

    avg_valence: float
    avg_energy: float

    positive_count: int
    neutral_count: int
    negative_count: int

    latest_valence: int
    latest_energy: int


# 오늘 첫 기록과 마지막 기록 사이의 변화
class MoodWithinDayChange(BaseModel):
    available: bool = False
    checkin_count: int = 0

    first_recorded_at: Optional[str] = None
    last_recorded_at: Optional[str] = None

    valence_delta: Optional[int] = None
    energy_delta: Optional[int] = None


# 분석 시작일 직전 14일의 개인 기준선
class MoodPersonalBaseline(BaseModel):
    status: Literal[
        "available",
        "insufficient",
        "unavailable",
    ] = "insufficient"

    window_days: int = 14
    checkin_count: int = 0
    active_days: int = 0

    avg_valence: Optional[float] = None
    avg_energy: Optional[float] = None

    valence_delta: Optional[float] = None
    energy_delta: Optional[float] = None


# 문장을 생성할 때 사용할 관찰 코드와 근거
class MoodEvidenceInsight(BaseModel):
    code: str

    evidence_count: int
    evidence_days: int

    emotion_codes: List[str] = Field(
        default_factory=list
    )
    trigger_codes: List[str] = Field(
        default_factory=list
    )


# 상세 분석 결과
class MoodDetailedInsights(BaseModel):
    version: int = 1

    observation: MoodObservation

    emotions: List[MoodEmotionDetail] = Field(
        default_factory=list
    )

    emotion_pairs: List[MoodEmotionPair] = Field(
        default_factory=list
    )

    triggers: List[MoodTriggerDetail] = Field(
        default_factory=list
    )

    within_day_change: MoodWithinDayChange = Field(
        default_factory=MoodWithinDayChange
    )

    baseline: MoodPersonalBaseline = Field(
        default_factory=MoodPersonalBaseline
    )

    insights: List[MoodEvidenceInsight] = Field(
        default_factory=list
    )

class MoodAnalysisFeedbackContext(BaseModel):
    reportKey: str
    analysisVersion: int
    token: str

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

    detailedInsights: Optional[
        MoodDetailedInsights
    ] = None

    feedbackContext: Optional[
        MoodAnalysisFeedbackContext
    ] = None

# 분석이 감정 이해에 도움이 되었는지 평가한다.
AnalysisFeedbackRating = Literal[
    "helpful",
    "partly_helpful",
    "not_helpful",
]


class AnalysisFeedbackLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=4096)


class AnalysisFeedbackInput(AnalysisFeedbackLookup):
    rating: AnalysisFeedbackRating


class AnalysisFeedbackResponse(BaseModel):
    reportKey: str
    rating: Optional[AnalysisFeedbackRating] = None
