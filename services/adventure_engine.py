
# services/adventure_engine.py

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

TOTAL_REGIONS = 8
STAGES_PER_REGION = 5
DISTANCE_PER_REGION = 18.0
MAX_DAILY_SPEED = 3.0


def daily_speed(energy: int) -> float:
    """Energy 1–5, capped at 3 map squares per day."""
    if not 1 <= energy <= 5:
        raise ValueError("Energy must be between 1 and 5")
    return float(min(energy, 3))


@dataclass
class JourneyState:
    region: int
    distance: float
    direction: str
    energy: int
    updated_at: datetime


def advance_journey(
    state: JourneyState,
    now: Optional[datetime] = None,
) -> JourneyState:
    """Advance using elapsed server time and the stored energy."""
    now = now or datetime.now(timezone.utc)

    if now.tzinfo is None or state.updated_at.tzinfo is None:
        raise ValueError("Timezone-aware timestamps required")

    elapsed_seconds = max(
        0.0,
        (now - state.updated_at).total_seconds(),
    )

    distance_added = (
        elapsed_seconds / 86400.0
    ) * daily_speed(state.energy)

    return JourneyState(
        region=state.region,
        distance=min(
            DISTANCE_PER_REGION,
            max(0.0, state.distance) + distance_added,
        ),
        direction=state.direction,
        energy=state.energy,
        updated_at=now,
    )


def change_energy(
    state: JourneyState,
    new_energy: int,
    now: Optional[datetime] = None,
) -> JourneyState:
    """Settle old-speed travel before applying new energy."""
    now = now or datetime.now(timezone.utc)
    advanced = advance_journey(state, now)

    return JourneyState(
        region=advanced.region,
        distance=advanced.distance,
        direction=advanced.direction,
        energy=int(daily_speed(new_energy))
        if new_energy <= 3 else new_energy,
        updated_at=now,
    )


def journey_progress(state: JourneyState) -> dict:
    distance = min(
        DISTANCE_PER_REGION,
        max(0.0, state.distance),
    )

    return {
        "region": state.region,
        "progress": round(
            distance / DISTANCE_PER_REGION, 4
        ),
        "arrived": distance >= DISTANCE_PER_REGION,
    }
