from __future__ import annotations

from collections.abc import Iterable

CANONICAL_SLED_DISTANCES_KM = frozenset({5, 10})
MAX_DAILY_DOG_DISTANCE_KM = 30


class WorkloadRuleViolation(ValueError):
    """Raised when actual sled workload violates a canonical domain rule."""


def add_daily_dog_distance(current_total_km: int, distance_km: int) -> int:
    """Return the new daily total, rejecting invalid sessions or totals over 30 km."""
    if current_total_km < 0:
        raise WorkloadRuleViolation("daily dog distance cannot be negative")
    if distance_km not in CANONICAL_SLED_DISTANCES_KM:
        raise WorkloadRuleViolation(
            f"sled session distance must be one of "
            f"{sorted(CANONICAL_SLED_DISTANCES_KM)} km"
        )

    new_total = current_total_km + distance_km
    if new_total > MAX_DAILY_DOG_DISTANCE_KM:
        raise WorkloadRuleViolation(
            f"daily dog distance {new_total} km exceeds {MAX_DAILY_DOG_DISTANCE_KM} km"
        )
    return new_total


def validate_daily_dog_distances(distances_km: Iterable[int]) -> int:
    """Validate a dog's actual sled sessions for one calendar date."""
    total = 0
    for distance_km in distances_km:
        total = add_daily_dog_distance(total, distance_km)
    return total
