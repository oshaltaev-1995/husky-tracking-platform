from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol, TypeVar

from app.models import Dog, HousingAssignment


class EffectivePeriod(Protocol):
    valid_from: date
    valid_to: date | None


PeriodT = TypeVar("PeriodT", bound=EffectivePeriod)


def effective_period(periods: Sequence[PeriodT], on_date: date) -> PeriodT | None:
    """Resolve a half-open effective period without leaking a later value."""
    return next(
        (
            period
            for period in periods
            if period.valid_from <= on_date
            and (period.valid_to is None or on_date < period.valid_to)
        ),
        None,
    )


@dataclass(frozen=True, slots=True)
class EffectiveDogState:
    """Shared dated state resolver for Dog Profile and Kennel Map projections."""

    on_date: date

    def lifecycle(self, dog: Dog) -> str | None:
        period = effective_period(dog.lifecycle_periods, self.on_date)
        return period.lifecycle_state if period else None

    def dog_class(
        self, dog: Dog, *, historical_fallback: bool = False
    ) -> tuple[str | None, bool]:
        period = effective_period(dog.class_periods, self.on_date)
        if period:
            return period.dog_class, False
        if not historical_fallback:
            return None, False
        historical = max(
            dog.class_periods, key=lambda row: row.valid_from, default=None
        )
        return (historical.dog_class if historical else None), historical is not None

    def availability(self, dog: Dog) -> str | None:
        period = effective_period(dog.availability_periods, self.on_date)
        return period.availability_state if period else None

    def housing(self, dog: Dog) -> HousingAssignment | None:
        return effective_period(dog.housing_assignments, self.on_date)
