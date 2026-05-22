from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class UserContext:
    """The user's current intent and location context."""

    mode: str
    address: str
    lat: float
    lon: float
    radius_m: int
    interests: tuple[str, ...]
    time_of_day: str
    weather: str | None = None


@dataclass(frozen=True)
class PickCard:
    """A single source-backed local opportunity / useful update card."""

    id: str
    card_type: str
    title: str
    description: str
    source_name: str
    source_url: str
    category: str
    lat: float | None = None
    lon: float | None = None
    location_name: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    source_reliability: float = 0.7
    freshness_score: float = 0.6
    business_submitted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_source(self) -> bool:
        return bool(self.source_url and self.source_url.startswith("http"))


@dataclass(frozen=True)
class RankedPick:
    """A pick card with computed ranking features."""

    card: PickCard
    score: float
    distance_m: float | None
    why_shown: str
    actions: tuple[str, ...] = ("Save", "Share", "Remind me", "Open source")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
