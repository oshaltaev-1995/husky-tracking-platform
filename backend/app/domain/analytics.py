from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkDistanceTotals:
    """Canonical per-participation distance totals shared by profile and analytics."""

    dog_starts: int
    dog_km: int
    starts_5km: int
    starts_10km: int
    average_km_per_start: float


def summarize_work_distances(distances: Iterable[int]) -> WorkDistanceTotals:
    values = list(distances)
    dog_km = sum(values)
    starts = len(values)
    return WorkDistanceTotals(
        dog_starts=starts,
        dog_km=dog_km,
        starts_5km=sum(value == 5 for value in values),
        starts_10km=sum(value == 10 for value in values),
        average_km_per_start=(round(dog_km / starts, 1) if starts else 0.0),
    )
