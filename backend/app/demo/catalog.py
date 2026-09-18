from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID, uuid5

from app.models.enums import (
    ArchiveReason,
    AvailabilityState,
    DogClass,
    DogSex,
    RelationshipKind,
)

DEMO_DATASET_VERSION = "winter-2025-2026-v1"
DEMO_RANDOM_SEED = 20260331
EXPECTED_SEMANTIC_CHECKSUM = (
    "2ad3418ecb5edad1d4676a9a6e0cf43b2cfbfa167c0218e96d9749fd12e24af2"
)
DEMO_NAMESPACE = UUID("9d947d11-4135-5d0d-a14e-3b06c71f5f6c")
MINIMUM_BREEDING_AGE_DAYS = 730

FORBIDDEN_STREAMLIT_NAMES = frozenset(
    {
        "Irbis",
        "Taiga",
        "Rikki",
        "Joha",
        "Lennon",
        "Blix",
        "Talvi",
        "Lumi",
        "Tesla",
        "Lara",
        "Jukki",
        "Vita",
        "Efir",
        "Sparki",
        "Vesta",
        "Lisa",
        "Prince",
        "Rover",
        "Landa",
        "Koni",
        "Monti",
        "Python",
        "Misha",
        "Graph",
        "Ilon",
        "Knox",
        "Kurt",
        "Marfa",
        "Whisky",
        "Ray",
    }
)


@dataclass(frozen=True, slots=True)
class DogSpec:
    name: str
    birth_date: date
    sex: DogSex
    litter_code: str | None
    neutered_on: date | None = None

    @property
    def public_id(self) -> UUID:
        return uuid5(DEMO_NAMESPACE, f"{DEMO_DATASET_VERSION}:dog:{self.name}")

    @property
    def photo_key(self) -> str:
        """Return the canonical media filename owned by this stable dog identity."""
        return f"{self.public_id}.webp"


@dataclass(frozen=True, slots=True)
class LitterSpec:
    code: str
    birth_date: date
    members: tuple[tuple[str, DogSex], ...]
    mother: str | None
    father: str | None
    notes: str


@dataclass(frozen=True, slots=True)
class ArchiveSpec:
    archive_date: date
    reason: ArchiveReason
    note: str


@dataclass(frozen=True, slots=True)
class StatusInterruption:
    state: AvailabilityState
    valid_from: date
    valid_to: date | None
    note: str


FOUNDATION_DOGS: tuple[DogSpec, ...] = (
    DogSpec("Aurora", date(2016, 1, 10), DogSex.FEMALE, None, date(2022, 9, 1)),
    DogSpec("Atlas", date(2016, 2, 20), DogSex.MALE, None, date(2020, 8, 1)),
    DogSpec("Freya", date(2016, 4, 18), DogSex.FEMALE, None, date(2021, 6, 1)),
    DogSpec("Fjord", date(2016, 5, 12), DogSex.MALE, None, date(2022, 10, 1)),
)

LITTER_SPECS: tuple[LitterSpec, ...] = (
    LitterSpec(
        "C",
        date(2018, 6, 15),
        (
            ("Cedar", DogSex.MALE),
            ("Cinder", DogSex.FEMALE),
            ("Cosmo", DogSex.MALE),
            ("Clover", DogSex.FEMALE),
            ("Coast", DogSex.MALE),
        ),
        "Aurora",
        None,
        "Foundation line with one external sire.",
    ),
    LitterSpec(
        "D",
        date(2019, 1, 2),
        (
            ("Dune", DogSex.MALE),
            ("Delta", DogSex.FEMALE),
            ("Django", DogSex.MALE),
            ("Daisy", DogSex.FEMALE),
            ("Drift", DogSex.MALE),
        ),
        "Freya",
        "Atlas",
        "Second independent foundation line.",
    ),
    LitterSpec(
        "H",
        date(2020, 5, 20),
        (
            ("Harbor", DogSex.MALE),
            ("Hazel", DogSex.FEMALE),
            ("Hugo", DogSex.MALE),
            ("Hilda", DogSex.FEMALE),
            ("Halo", DogSex.FEMALE),
        ),
        "Aurora",
        "Fjord",
        "Foundation cross retained as a separate branch.",
    ),
    LitterSpec(
        "K",
        date(2021, 2, 15),
        (
            ("Koda", DogSex.MALE),
            ("Kira", DogSex.FEMALE),
            ("Kenzo", DogSex.MALE),
            ("Kaia", DogSex.FEMALE),
            ("Kepler", DogSex.MALE),
            ("Kismet", DogSex.FEMALE),
        ),
        "Clover",
        "Django",
        "First represented second-generation cross.",
    ),
    LitterSpec(
        "M",
        date(2022, 4, 14),
        (
            ("Maple", DogSex.FEMALE),
            ("Magnus", DogSex.MALE),
            ("Mabel", DogSex.FEMALE),
            ("Milo", DogSex.MALE),
            ("Mistral", DogSex.MALE),
        ),
        "Delta",
        "Coast",
        "D and C family-line cross.",
    ),
    LitterSpec(
        "N",
        date(2023, 3, 1),
        (
            ("Nova", DogSex.FEMALE),
            ("Niko", DogSex.MALE),
            ("Nala", DogSex.FEMALE),
            ("Nimbus", DogSex.MALE),
            ("Nora", DogSex.FEMALE),
            ("North", DogSex.MALE),
        ),
        "Hazel",
        "Koda",
        "Generation-three branch joining H and K lines.",
    ),
    LitterSpec(
        "O",
        date(2024, 6, 20),
        (
            ("Orion", DogSex.MALE),
            ("Olive", DogSex.FEMALE),
            ("Otis", DogSex.MALE),
            ("Opal", DogSex.FEMALE),
            ("Onyx", DogSex.MALE),
            ("Oona", DogSex.FEMALE),
        ),
        "Kira",
        "Magnus",
        "Generation-three K and M family-line cross.",
    ),
    LitterSpec(
        "S",
        date(2025, 3, 10),
        (
            ("Sanchez", DogSex.MALE),
            ("Sergio", DogSex.MALE),
            ("Sampo", DogSex.MALE),
            ("Sancho", DogSex.MALE),
            ("Siri", DogSex.FEMALE),
            ("Sophie", DogSex.FEMALE),
            ("Storm", DogSex.MALE),
            ("Sage", DogSex.FEMALE),
        ),
        "Maple",
        "Nimbus",
        "Canonical owner-supplied S-litter.",
    ),
    LitterSpec(
        "T",
        date(2026, 1, 12),
        (
            ("Taro", DogSex.MALE),
            ("Tessa", DogSex.FEMALE),
            ("Theo", DogSex.MALE),
            ("Tindra", DogSex.FEMALE),
            ("Toast", DogSex.MALE),
        ),
        "Nova",
        "Milo",
        "First 2026 puppy litter.",
    ),
    LitterSpec(
        "V",
        date(2026, 2, 18),
        (
            ("Vega", DogSex.FEMALE),
            ("Valor", DogSex.MALE),
            ("Violet", DogSex.FEMALE),
            ("Viggo", DogSex.MALE),
            ("Viva", DogSex.FEMALE),
        ),
        "Nora",
        "Kenzo",
        "Second 2026 puppy litter.",
    ),
)

NEUTERED_ON: dict[str, date] = {
    "Cedar": date(2022, 8, 1),
    "Cinder": date(2019, 10, 1),
    "Cosmo": date(2022, 8, 2),
    "Dune": date(2023, 4, 1),
    "Daisy": date(2023, 4, 2),
    "Drift": date(2023, 4, 3),
    "Harbor": date(2024, 1, 2),
    "Hugo": date(2024, 1, 3),
    "Hilda": date(2022, 1, 3),
    "Halo": date(2024, 1, 4),
    "Kaia": date(2025, 2, 2),
    "Kepler": date(2025, 2, 3),
    "Kismet": date(2025, 2, 4),
    "Mabel": date(2025, 5, 1),
    "Mistral": date(2025, 5, 2),
    "Niko": date(2025, 5, 3),
    "Nala": date(2025, 5, 4),
    "North": date(2025, 5, 5),
    "Olive": date(2025, 9, 1),
    "Otis": date(2025, 9, 2),
    "Opal": date(2025, 9, 3),
    "Onyx": date(2025, 9, 4),
    "Oona": date(2025, 9, 5),
}


def _litter_dogs() -> tuple[DogSpec, ...]:
    return tuple(
        DogSpec(
            name=name,
            birth_date=litter.birth_date,
            sex=sex,
            litter_code=litter.code,
            neutered_on=NEUTERED_ON.get(name),
        )
        for litter in LITTER_SPECS
        for name, sex in litter.members
    )


DOG_SPECS: tuple[DogSpec, ...] = FOUNDATION_DOGS + _litter_dogs()
DOG_BY_NAME: dict[str, DogSpec] = {dog.name: dog for dog in DOG_SPECS}

ARCHIVE_SPECS: dict[str, ArchiveSpec] = {
    "Cinder": ArchiveSpec(
        date(2020, 8, 20),
        ArchiveReason.REHOMED_TO_GUIDE,
        "Placed in a fictional guide program.",
    ),
    "Coast": ArchiveSpec(
        date(2025, 7, 10),
        ArchiveReason.DECEASED,
        "Died naturally after a brief decline.",
    ),
    "Django": ArchiveSpec(
        date(2025, 12, 15),
        ArchiveReason.EUTHANIZED,
        "Humane fictional end-of-life record.",
    ),
    "Hilda": ArchiveSpec(
        date(2024, 3, 8),
        ArchiveReason.REHOMED_TO_GUIDE,
        "Placed in a fictional guide program.",
    ),
    "Kismet": ArchiveSpec(
        date(2025, 9, 4), ArchiveReason.DECEASED, "Died naturally; synthetic record."
    ),
    "Mabel": ArchiveSpec(
        date(2025, 11, 12),
        ArchiveReason.REHOMED_TO_GUIDE,
        "Placed in a fictional guide program.",
    ),
    "Nimbus": ArchiveSpec(
        date(2026, 1, 15),
        ArchiveReason.EUTHANIZED,
        "Humane fictional end-of-life record.",
    ),
    "Oona": ArchiveSpec(
        date(2025, 10, 22), ArchiveReason.DECEASED, "Died naturally; synthetic record."
    ),
    "Sage": ArchiveSpec(
        date(2025, 12, 20),
        ArchiveReason.REHOMED_TO_GUIDE,
        "Placed in a fictional guide program.",
    ),
    "Sergio": ArchiveSpec(
        date(2026, 2, 20),
        ArchiveReason.EUTHANIZED,
        "Humane fictional end-of-life record.",
    ),
}

STATUS_INTERRUPTION_SPECS: dict[str, tuple[StatusInterruption, ...]] = {
    "Hazel": (
        StatusInterruption(
            AvailabilityState.INJURED,
            date(2026, 3, 15),
            None,
            "Minor fictional paw injury under observation.",
        ),
    ),
    "Orion": (
        StatusInterruption(
            AvailabilityState.REST,
            date(2026, 3, 25),
            None,
            "Planned recovery block after training progression.",
        ),
    ),
    "Cedar": (
        StatusInterruption(
            AvailabilityState.RESTRICTED,
            date(2026, 3, 20),
            None,
            "Restricted from sled work pending fictional review.",
        ),
    ),
    "Fjord": (
        StatusInterruption(
            AvailabilityState.RETIRED,
            date(2026, 2, 15),
            None,
            "Retired from work while remaining an active kennel resident.",
        ),
    ),
    "Maple": (
        StatusInterruption(
            AvailabilityState.INJURED,
            date(2025, 12, 20),
            date(2026, 1, 10),
            "Short fictional shoulder recovery.",
        ),
    ),
    "Koda": (
        StatusInterruption(
            AvailabilityState.REST,
            date(2026, 1, 18),
            date(2026, 1, 25),
            "Scheduled recovery week.",
        ),
    ),
    "Delta": (
        StatusInterruption(
            AvailabilityState.RESTRICTED,
            date(2026, 2, 1),
            date(2026, 2, 12),
            "Temporary light-duty restriction; no sled starts in P2.",
        ),
    ),
    "Aurora": (
        StatusInterruption(
            AvailabilityState.REST,
            date(2026, 3, 5),
            date(2026, 3, 10),
            "Planned recovery interval.",
        ),
    ),
}

PREFERRED_PAIR_SPECS: tuple[tuple[str, str], ...] = (
    ("Aurora", "Atlas"),
    ("Freya", "Fjord"),
    ("Cedar", "Clover"),
    ("Delta", "Dune"),
    ("Harbor", "Hazel"),
    ("Koda", "Kira"),
    ("Maple", "Magnus"),
    ("Nova", "Niko"),
    ("Orion", "Olive"),
    ("Sanchez", "Sophie"),
)

HARD_CONFLICT_SPECS: tuple[tuple[str, str], ...] = (
    ("Atlas", "Fjord"),
    ("Cedar", "Dune"),
    ("Hazel", "Koda"),
    ("Maple", "Nimbus"),
    ("Nova", "North"),
    ("Orion", "Onyx"),
)

RELATIONSHIP_SPECS: tuple[tuple[str, str, RelationshipKind], ...] = tuple(
    (a, b, RelationshipKind.PREFERRED_PAIR) for a, b in PREFERRED_PAIR_SPECS
) + tuple((a, b, RelationshipKind.HARD_CONFLICT) for a, b in HARD_CONFLICT_SPECS)

HIGH_WORKLOAD_DOGS = frozenset({"Aurora", "Atlas", "Freya"})
UNDERUSED_DOGS = frozenset({"Cedar", "Delta", "Harbor"})


def archive_spec_for(name: str) -> ArchiveSpec | None:
    return ARCHIVE_SPECS.get(name)


def current_class_for(dog: DogSpec) -> DogClass | None:
    if dog.name in ARCHIVE_SPECS:
        return None
    year = dog.birth_date.year
    if year == 2026:
        return DogClass.PUPPY
    if year == 2025:
        return DogClass.JUNIOR
    if year == 2024:
        return DogClass.TRAINING
    if year == 2023 and dog.name in {"Nova", "Niko", "Nala"}:
        return DogClass.TRAINING
    return DogClass.STANDARD


def add_years(value: date, years: int) -> date:
    return value.replace(year=value.year + years)


def class_period_specs(dog: DogSpec) -> tuple[tuple[DogClass, date, date | None], ...]:
    """Return non-overlapping class periods ending at archive when applicable."""
    end = ARCHIVE_SPECS.get(dog.name)
    terminal = end.archive_date if end else None
    transitions: list[tuple[DogClass, date]] = [(DogClass.PUPPY, dog.birth_date)]

    if dog.birth_date.year <= 2025:
        transitions.append((DogClass.JUNIOR, add_years(dog.birth_date, 1)))
    if dog.birth_date.year <= 2024:
        training_start = add_years(dog.birth_date, 2)
        if dog.birth_date.year == 2024:
            training_start = date(2025, 12, 1)
        transitions.append((DogClass.TRAINING, training_start))
    if dog.birth_date.year <= 2022:
        transitions.append((DogClass.STANDARD, add_years(dog.birth_date, 3)))
    elif dog.birth_date.year == 2023 and dog.name in {"Nora", "North"}:
        transitions.append((DogClass.STANDARD, date(2026, 2, 1)))

    transitions.sort(key=lambda item: item[1])
    periods: list[tuple[DogClass, date, date | None]] = []
    for index, (dog_class, valid_from) in enumerate(transitions):
        if terminal is not None and valid_from >= terminal:
            break
        next_from = transitions[index + 1][1] if index + 1 < len(transitions) else None
        valid_to = (
            min(next_from, terminal)
            if next_from and terminal
            else next_from or terminal
        )
        periods.append((dog_class, valid_from, valid_to))
    return tuple(periods)


def availability_period_specs(
    dog: DogSpec, season_start: date
) -> tuple[tuple[AvailabilityState, date, date | None, str | None], ...]:
    archive = ARCHIVE_SPECS.get(dog.name)
    if archive:
        valid_from = max(dog.birth_date, archive.archive_date - timedelta(days=180))
        return ((AvailabilityState.AVAILABLE, valid_from, archive.archive_date, None),)

    valid_from = max(dog.birth_date, season_start)
    interruptions = STATUS_INTERRUPTION_SPECS.get(dog.name, ())
    periods: list[tuple[AvailabilityState, date, date | None, str | None]] = []
    cursor = valid_from
    for interruption in interruptions:
        if cursor < interruption.valid_from:
            periods.append(
                (AvailabilityState.AVAILABLE, cursor, interruption.valid_from, None)
            )
        periods.append(
            (
                interruption.state,
                interruption.valid_from,
                interruption.valid_to,
                interruption.note,
            )
        )
        if interruption.valid_to is None:
            return tuple(periods)
        cursor = interruption.valid_to
    periods.append((AvailabilityState.AVAILABLE, cursor, None, None))
    return tuple(periods)
