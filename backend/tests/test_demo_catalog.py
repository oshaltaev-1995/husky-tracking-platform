from collections import Counter

from app.demo.catalog import (
    ARCHIVE_SPECS,
    DEMO_DATASET_VERSION,
    DOG_SPECS,
    FORBIDDEN_STREAMLIT_NAMES,
    LITTER_SPECS,
    MINIMUM_BREEDING_AGE_DAYS,
)


def test_curated_catalog_has_canonical_population_and_no_forbidden_names() -> None:
    names = [dog.name for dog in DOG_SPECS]
    photo_keys = [dog.photo_key for dog in DOG_SPECS]

    assert DEMO_DATASET_VERSION == "winter-2025-2026-v1"
    assert len(names) == 60
    assert len(set(names)) == 60
    assert len(set(photo_keys)) == 60
    assert all(
        key == f"{dog.public_id}.webp"
        for key, dog in zip(photo_keys, DOG_SPECS, strict=True)
    )
    assert set(names).isdisjoint(FORBIDDEN_STREAMLIT_NAMES)
    assert Counter(dog.birth_date.year for dog in DOG_SPECS) == {
        2016: 4,
        2018: 5,
        2019: 5,
        2020: 5,
        2021: 6,
        2022: 5,
        2023: 6,
        2024: 6,
        2025: 8,
        2026: 10,
    }
    assert len(ARCHIVE_SPECS) == 10


def test_litters_use_curated_names_and_plausible_parents() -> None:
    dogs = {dog.name: dog for dog in DOG_SPECS}
    litter_codes = {litter.code for litter in LITTER_SPECS}

    assert len(LITTER_SPECS) == 10
    assert len(litter_codes) == len(LITTER_SPECS)
    assert [len(litter.members) for litter in LITTER_SPECS[-2:]] == [5, 5]
    assert {
        name for name, _ in next(row for row in LITTER_SPECS if row.code == "S").members
    } == {
        "Sanchez",
        "Sergio",
        "Sampo",
        "Sancho",
        "Siri",
        "Sophie",
        "Storm",
        "Sage",
    }
    for litter in LITTER_SPECS:
        assert all(name.startswith(litter.code) for name, _ in litter.members)
        for parent_name in (litter.mother, litter.father):
            if parent_name:
                assert (litter.birth_date - dogs[parent_name].birth_date).days >= (
                    MINIMUM_BREEDING_AGE_DAYS
                )
