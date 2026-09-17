from __future__ import annotations

import json
import re
import statistics
import struct
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.demo.catalog import (
    DEMO_DATASET_VERSION,
    DOG_SPECS,
    FORBIDDEN_STREAMLIT_NAMES,
    LITTER_SPECS,
)
from app.media.manifest_builder import (
    MEDIA_HEIGHT,
    MEDIA_MANIFEST_VERSION,
    MEDIA_REFERENCE_DATE,
    MEDIA_WIDTH,
    build_manifest,
)

CANONICAL_FILENAME = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}"
    r"-[0-9a-f]{12}\.webp$",
    re.IGNORECASE,
)


class ManifestValidationError(ValueError):
    """Raised when media identity or assets do not match the canonical contract."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgeAtReference(StrictModel):
    years: int = Field(ge=0)
    months: int = Field(ge=0, le=11)
    label: str = Field(min_length=1)


class ParentIdentity(StrictModel):
    dog_id: UUID
    name: str = Field(min_length=1)


class VisualTraits(StrictModel):
    coat_base: str = Field(min_length=1)
    coat_secondary: str = Field(min_length=1)
    facial_marking: str = Field(min_length=1)
    eye_color: str = Field(min_length=1)
    coat_length: str = Field(min_length=1)
    build: str = Field(min_length=1)
    ear_presentation: str = Field(min_length=1)
    tail_appearance: str = Field(min_length=1)
    approximate_visual_age: str = Field(min_length=1)
    distinctive_marking: str = Field(min_length=1)
    family_resemblance: str = Field(min_length=1)
    portrait_character: str = Field(min_length=1)


class DogMediaEntry(StrictModel):
    dog_id: UUID
    name: str = Field(min_length=1)
    sex: Literal["female", "male"]
    birth_date: date
    age_at_reference: AgeAtReference
    operational_class: Literal["puppy", "junior", "training", "standard"]
    litter_code: str | None
    mother: ParentIdentity | None
    father: ParentIdentity | None
    lifecycle: Literal["active", "archived"]
    target_filename: str = Field(min_length=1)
    visual_traits: VisualTraits
    generation_brief: str = Field(min_length=100)


class AssetContract(StrictModel):
    repository_directory: str
    public_url_prefix: str
    format: Literal["webp"]
    width_px: int
    height_px: int
    aspect_ratio: Literal["3:4"]
    cache_version: str
    target_file_size_kb: int = Field(gt=0)
    review_file_size_kb: int = Field(gt=0)


class DogMediaManifest(StrictModel):
    manifest_version: str
    dataset_version: str
    reference_date: date
    asset_contract: AssetContract
    dogs: list[DogMediaEntry]


@dataclass(frozen=True, slots=True)
class AssetValidationReport:
    expected_files: int
    found_files: int
    minimum_size_kb: float
    median_size_kb: float
    maximum_size_kb: float


def load_manifest(path: Path) -> DogMediaManifest:
    try:
        return DogMediaManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise ManifestValidationError(f"Cannot load media manifest: {exc}") from exc


def validate_manifest(manifest: DogMediaManifest) -> None:
    errors: list[str] = []
    if manifest.manifest_version != MEDIA_MANIFEST_VERSION:
        errors.append(f"manifest_version must be {MEDIA_MANIFEST_VERSION}")
    if manifest.dataset_version != DEMO_DATASET_VERSION:
        errors.append(f"dataset_version must be {DEMO_DATASET_VERSION}")
    if manifest.reference_date != MEDIA_REFERENCE_DATE:
        errors.append(f"reference_date must be {MEDIA_REFERENCE_DATE}")

    contract = manifest.asset_contract
    if contract.repository_directory != "frontend/public/media/dogs":
        errors.append("asset directory must be frontend/public/media/dogs")
    if contract.public_url_prefix != "/media/dogs/":
        errors.append("public URL prefix must be /media/dogs/")
    if (contract.width_px, contract.height_px) != (MEDIA_WIDTH, MEDIA_HEIGHT):
        errors.append(f"asset dimensions must be {MEDIA_WIDTH}x{MEDIA_HEIGHT}")
    if contract.cache_version != MEDIA_MANIFEST_VERSION:
        errors.append("cache version must match manifest version")

    if len(manifest.dogs) != 60:
        errors.append(f"expected 60 manifest entries, found {len(manifest.dogs)}")
    if len(DOG_SPECS) != 60:
        errors.append(f"canonical dog catalog has {len(DOG_SPECS)} dogs, expected 60")

    ids = [entry.dog_id for entry in manifest.dogs]
    names = [entry.name for entry in manifest.dogs]
    filenames = [entry.target_filename.casefold() for entry in manifest.dogs]
    if len(ids) != len(set(ids)):
        errors.append("dog IDs must be unique")
    if len(names) != len({name.casefold() for name in names}):
        errors.append("dog names must be unique")
    if len(filenames) != len(set(filenames)):
        errors.append("target filenames must be unique")
    if len({entry.generation_brief for entry in manifest.dogs}) != len(manifest.dogs):
        errors.append("generation briefs must be unique")

    forbidden = {name.casefold() for name in FORBIDDEN_STREAMLIT_NAMES}
    reused = sorted(name for name in names if name.casefold() in forbidden)
    if reused:
        errors.append("forbidden real-kennel names present: " + ", ".join(reused))

    expected = build_manifest()
    expected_by_id = {item["dog_id"]: item for item in expected["dogs"]}
    actual_by_id = {str(item.dog_id): item for item in manifest.dogs}
    missing = sorted(set(expected_by_id) - set(actual_by_id))
    unknown = sorted(set(actual_by_id) - set(expected_by_id))
    if missing:
        errors.append("missing canonical dog IDs: " + ", ".join(missing))
    if unknown:
        errors.append("unknown dog IDs: " + ", ".join(unknown))

    for dog_id in sorted(set(expected_by_id) & set(actual_by_id)):
        expected_entry = expected_by_id[dog_id]
        actual_entry = actual_by_id[dog_id].model_dump(mode="json")
        if actual_entry != expected_entry:
            errors.append(
                f"manifest identity mismatch for {expected_entry['name']} ({dog_id})"
            )
        filename = actual_entry["target_filename"]
        if not CANONICAL_FILENAME.fullmatch(filename):
            errors.append(f"invalid canonical filename for {expected_entry['name']}")
        if filename != f"{dog_id}.webp":
            errors.append(f"filename does not match UUID for {expected_entry['name']}")

    litter_codes = {litter.code for litter in LITTER_SPECS}
    for entry in manifest.dogs:
        if entry.litter_code:
            if entry.litter_code not in litter_codes:
                errors.append(f"unknown litter {entry.litter_code} for {entry.name}")
            elif not entry.name.casefold().startswith(entry.litter_code.casefold()):
                errors.append(
                    f"litter member {entry.name} must start with {entry.litter_code}"
                )

    active_count = sum(item.lifecycle == "active" for item in manifest.dogs)
    archived_count = sum(item.lifecycle == "archived" for item in manifest.dogs)
    if (active_count, archived_count) != (50, 10):
        errors.append(
            "manifest lifecycle coverage must be 50 active and 10 archived, found "
            f"{active_count} active and {archived_count} archived"
        )

    if errors:
        raise ManifestValidationError("\n".join(errors))


def _webp_dimensions(path: Path) -> tuple[int, int]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ManifestValidationError(f"cannot read {path.name}: {exc}") from exc
    if not data:
        raise ManifestValidationError(f"{path.name} is zero bytes")
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ManifestValidationError(f"{path.name} is not a WebP RIFF container")
    declared_size = struct.unpack_from("<I", data, 4)[0] + 8
    if declared_size != len(data):
        raise ManifestValidationError(f"{path.name} has an invalid RIFF length")

    offset = 12
    container_dimensions: tuple[int, int] | None = None
    frame_dimensions: tuple[int, int] | None = None
    has_image_payload = False
    while offset + 8 <= len(data):
        chunk_type = data[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        if payload_end > len(data):
            raise ManifestValidationError(f"{path.name} has a truncated WebP chunk")
        payload = data[payload_start:payload_end]
        if chunk_type == b"VP8X" and len(payload) >= 10:
            width = int.from_bytes(payload[4:7], "little") + 1
            height = int.from_bytes(payload[7:10], "little") + 1
            container_dimensions = (width, height)
        elif chunk_type == b"VP8 " and len(payload) >= 10:
            if payload[3:6] != b"\x9d\x01\x2a":
                raise ManifestValidationError(f"{path.name} has an invalid VP8 frame")
            width = int.from_bytes(payload[6:8], "little") & 0x3FFF
            height = int.from_bytes(payload[8:10], "little") & 0x3FFF
            frame_dimensions = (width, height)
            has_image_payload = True
        elif chunk_type == b"VP8L" and len(payload) >= 5:
            if payload[0] != 0x2F:
                raise ManifestValidationError(f"{path.name} has an invalid VP8L frame")
            bits = int.from_bytes(payload[1:5], "little")
            frame_dimensions = (
                (bits & 0x3FFF) + 1,
                ((bits >> 14) & 0x3FFF) + 1,
            )
            has_image_payload = True
        offset = payload_end + (chunk_size % 2)

    if not has_image_payload or frame_dimensions is None:
        raise ManifestValidationError(f"{path.name} has no readable WebP image payload")
    if container_dimensions and container_dimensions != frame_dimensions:
        raise ManifestValidationError(
            f"{path.name} has inconsistent WebP container and frame dimensions"
        )
    return container_dimensions or frame_dimensions


def validate_assets(
    manifest: DogMediaManifest,
    asset_directory: Path,
    *,
    require_all: bool,
    strict: bool,
) -> AssetValidationReport:
    expected = {entry.target_filename for entry in manifest.dogs}
    if not asset_directory.exists():
        if require_all:
            raise ManifestValidationError(
                f"asset directory does not exist: {asset_directory}"
            )
        return AssetValidationReport(len(expected), 0, 0.0, 0.0, 0.0)

    found_paths = {
        path.name: path
        for path in asset_directory.iterdir()
        if path.is_file() and not path.name.startswith(".")
    }
    found = set(found_paths)
    errors: list[str] = []
    missing = sorted(expected - found)
    extras = sorted(found - expected)
    if require_all and missing:
        errors.append(f"missing {len(missing)} expected files: " + ", ".join(missing))
    if strict and extras:
        errors.append("unexpected files: " + ", ".join(extras))

    sizes: list[int] = []
    for filename in sorted(expected & found):
        path = found_paths[filename]
        try:
            dimensions = _webp_dimensions(path)
        except ManifestValidationError as exc:
            errors.append(str(exc))
            continue
        if dimensions != (MEDIA_WIDTH, MEDIA_HEIGHT):
            errors.append(
                f"{filename} is {dimensions[0]}x{dimensions[1]}, expected "
                f"{MEDIA_WIDTH}x{MEDIA_HEIGHT}"
            )
        sizes.append(path.stat().st_size)

    if errors:
        raise ManifestValidationError("\n".join(errors))
    size_kb = [size / 1024 for size in sizes]
    return AssetValidationReport(
        expected_files=len(expected),
        found_files=len(expected & found),
        minimum_size_kb=round(min(size_kb), 1) if size_kb else 0.0,
        median_size_kb=round(float(statistics.median(size_kb)), 1) if size_kb else 0.0,
        maximum_size_kb=round(max(size_kb), 1) if size_kb else 0.0,
    )
