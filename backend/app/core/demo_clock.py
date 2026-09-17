from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class DemoClock:
    """Single source of time for all demo-domain calculations."""

    season_start: date
    season_end: date
    reference_date: date
    season_label: str = "Demo season — Winter 2025–2026"

    @classmethod
    def from_settings(cls, settings: Settings) -> DemoClock:
        return cls(
            season_start=settings.demo_season_start,
            season_end=settings.demo_season_end,
            reference_date=settings.demo_reference_date,
        )
