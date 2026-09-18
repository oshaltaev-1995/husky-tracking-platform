from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from app.demo.catalog import (
    ARCHIVE_SPECS,
    DEMO_DATASET_VERSION,
    DOG_BY_NAME,
    DOG_SPECS,
    LITTER_SPECS,
    class_period_specs,
)
from app.media.identity_catalog import VISUAL_IDENTITIES, VisualIdentity

MEDIA_MANIFEST_VERSION = "dog-media-v1"
MEDIA_REFERENCE_DATE = date(2026, 3, 31)
MEDIA_WIDTH = 1086
MEDIA_HEIGHT = 1448


def _age_at(birth_date: date) -> dict[str, int | str]:
    months = (MEDIA_REFERENCE_DATE.year - birth_date.year) * 12
    months += MEDIA_REFERENCE_DATE.month - birth_date.month
    if MEDIA_REFERENCE_DATE.day < birth_date.day:
        months -= 1
    years, remaining_months = divmod(max(months, 0), 12)
    if years and remaining_months:
        year_word = "year" if years == 1 else "years"
        month_word = "month" if remaining_months == 1 else "months"
        label = f"{years} {year_word}, {remaining_months} {month_word}"
    elif years:
        label = f"{years} year" if years == 1 else f"{years} years"
    else:
        label = (
            f"{remaining_months} month"
            if remaining_months == 1
            else f"{remaining_months} months"
        )
    return {"years": years, "months": remaining_months, "label": label}


def _parent(name: str | None) -> dict[str, str] | None:
    if name is None:
        return None
    dog = DOG_BY_NAME[name]
    return {"dog_id": str(dog.public_id), "name": dog.name}


def _generation_brief(name: str, sex: str, identity: VisualIdentity) -> str:
    return (
        f"Portray {name}, a {sex} northern working sled dog at the "
        f"{identity.approximate_visual_age} stage, with {identity.build} proportions, "
        f"a {identity.coat_length} {identity.coat_base} and "
        f"{identity.coat_secondary} coat, "
        f"{identity.facial_marking}, and {identity.eye_color} eyes. "
        f"Show {identity.distinctive_marking}; {identity.family_resemblance}. "
        f"Use {identity.portrait_character}. One dog only, full body with all four "
        "anatomically correct legs, natural paws, ears, and complete tail visible, "
        "standing on textured snow in soft northern daylight; realistic modern "
        "outdoor dog photography with no person, other dog, text, watermark, frame, "
        "leash, harness, branded gear, or malformed anatomy."
    )


def build_manifest() -> dict[str, Any]:
    litter_by_code = {litter.code: litter for litter in LITTER_SPECS}
    dogs: list[dict[str, Any]] = []
    for dog in DOG_SPECS:
        identity = VISUAL_IDENTITIES[dog.name]
        litter = litter_by_code.get(dog.litter_code) if dog.litter_code else None
        final_class = class_period_specs(dog)[-1][0].value
        dogs.append(
            {
                "dog_id": str(dog.public_id),
                "name": dog.name,
                "sex": dog.sex.value,
                "birth_date": dog.birth_date.isoformat(),
                "age_at_reference": _age_at(dog.birth_date),
                "operational_class": final_class,
                "litter_code": dog.litter_code,
                "mother": _parent(litter.mother if litter else None),
                "father": _parent(litter.father if litter else None),
                "lifecycle": "archived" if dog.name in ARCHIVE_SPECS else "active",
                "target_filename": dog.photo_key,
                "visual_traits": {
                    "coat_base": identity.coat_base,
                    "coat_secondary": identity.coat_secondary,
                    "facial_marking": identity.facial_marking,
                    "eye_color": identity.eye_color,
                    "coat_length": identity.coat_length,
                    "build": identity.build,
                    "ear_presentation": identity.ear_presentation,
                    "tail_appearance": identity.tail_appearance,
                    "approximate_visual_age": identity.approximate_visual_age,
                    "distinctive_marking": identity.distinctive_marking,
                    "family_resemblance": identity.family_resemblance,
                    "portrait_character": identity.portrait_character,
                },
                "generation_brief": _generation_brief(
                    dog.name, dog.sex.value, identity
                ),
            }
        )
    return {
        "manifest_version": MEDIA_MANIFEST_VERSION,
        "dataset_version": DEMO_DATASET_VERSION,
        "reference_date": MEDIA_REFERENCE_DATE.isoformat(),
        "asset_contract": {
            "repository_directory": "frontend/public/media/dogs",
            "public_url_prefix": "/media/dogs/",
            "format": "webp",
            "width_px": MEDIA_WIDTH,
            "height_px": MEDIA_HEIGHT,
            "aspect_ratio": "3:4",
            "cache_version": MEDIA_MANIFEST_VERSION,
            "target_file_size_kb": 300,
            "review_file_size_kb": 500,
        },
        "dogs": dogs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild the reviewable dog-media manifest from the curated catalog."
        )
    )
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(build_manifest(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
