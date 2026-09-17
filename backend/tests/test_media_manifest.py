from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.media.manifest_builder import MEDIA_HEIGHT, MEDIA_WIDTH, build_manifest
from app.media.validation import (
    DogMediaManifest,
    ManifestValidationError,
    load_manifest,
    validate_assets,
    validate_manifest,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "docs" / "dog-media-manifest.json"


def _manifest(payload: dict[str, Any] | None = None) -> DogMediaManifest:
    return DogMediaManifest.model_validate(payload or build_manifest())


def _webp(width: int, height: int) -> bytes:
    vp8x = (
        b"VP8X"
        + struct.pack("<I", 10)
        + b"\0\0\0\0"
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )
    vp8_payload = (
        b"\0\0\0"
        + b"\x9d\x01\x2a"
        + width.to_bytes(2, "little")
        + height.to_bytes(2, "little")
    )
    vp8 = b"VP8 " + struct.pack("<I", len(vp8_payload)) + vp8_payload
    body = b"WEBP" + vp8x + vp8
    return b"RIFF" + struct.pack("<I", len(body)) + body


def test_committed_manifest_matches_all_canonical_dogs() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    validate_manifest(manifest)
    assert len(manifest.dogs) == 60
    assert sum(dog.lifecycle == "active" for dog in manifest.dogs) == 50
    assert sum(dog.lifecycle == "archived" for dog in manifest.dogs) == 10
    assert len({dog.target_filename for dog in manifest.dogs}) == 60


def test_manifest_rejects_missing_dog() -> None:
    payload = build_manifest()
    removed = payload["dogs"].pop()
    with pytest.raises(ManifestValidationError, match="expected 60 manifest entries"):
        validate_manifest(_manifest(payload))
    assert removed["name"] == "Viva"


def test_manifest_rejects_duplicate_filename() -> None:
    payload = build_manifest()
    payload["dogs"][1]["target_filename"] = payload["dogs"][0]["target_filename"]
    with pytest.raises(
        ManifestValidationError, match="target filenames must be unique"
    ):
        validate_manifest(_manifest(payload))


def test_manifest_rejects_wrong_uuid_mapping() -> None:
    payload = build_manifest()
    payload["dogs"][0]["dog_id"] = str(uuid4())
    with pytest.raises(ManifestValidationError, match="missing canonical dog IDs"):
        validate_manifest(_manifest(payload))


def test_manifest_rejects_wrong_file_extension() -> None:
    payload = build_manifest()
    payload["dogs"][0]["target_filename"] = "9422673b-331b-5e72-a700-5fff0574a209.jpg"
    with pytest.raises(ManifestValidationError, match="invalid canonical filename"):
        validate_manifest(_manifest(payload))


def test_manifest_rejects_forbidden_real_kennel_name() -> None:
    payload = build_manifest()
    payload["dogs"][0]["name"] = "Irbis"
    with pytest.raises(ManifestValidationError, match="forbidden real-kennel names"):
        validate_manifest(_manifest(payload))


def test_manifest_schema_rejects_a_missing_required_trait() -> None:
    payload = build_manifest()
    del payload["dogs"][0]["visual_traits"]["eye_color"]
    with pytest.raises(ValidationError, match="eye_color"):
        _manifest(payload)


def test_load_manifest_reports_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"manifest_version": "dog-media-v1"}), encoding="utf-8")
    with pytest.raises(ManifestValidationError, match="Cannot load media manifest"):
        load_manifest(path)


def test_asset_validation_accepts_exact_webp_contract(tmp_path: Path) -> None:
    manifest = _manifest().model_copy(update={"dogs": [_manifest().dogs[0]]})
    filename = manifest.dogs[0].target_filename
    (tmp_path / filename).write_bytes(_webp(MEDIA_WIDTH, MEDIA_HEIGHT))
    report = validate_assets(manifest, tmp_path, require_all=True, strict=True)
    assert report.expected_files == 1
    assert report.found_files == 1
    assert report.maximum_size_kb == 0.0  # tiny structural fixture rounds below 0.1 KB


def test_asset_validation_rejects_wrong_dimensions(tmp_path: Path) -> None:
    manifest = _manifest().model_copy(update={"dogs": [_manifest().dogs[0]]})
    filename = manifest.dogs[0].target_filename
    (tmp_path / filename).write_bytes(_webp(800, 1200))
    with pytest.raises(ManifestValidationError, match="expected 1086x1448"):
        validate_assets(manifest, tmp_path, require_all=True, strict=True)


def test_asset_validation_rejects_corrupt_missing_and_extra_files(
    tmp_path: Path,
) -> None:
    manifest = _manifest().model_copy(update={"dogs": [_manifest().dogs[0]]})
    filename = manifest.dogs[0].target_filename
    (tmp_path / filename).write_bytes(b"")
    (tmp_path / "extra.webp").write_bytes(_webp(MEDIA_WIDTH, MEDIA_HEIGHT))
    with pytest.raises(ManifestValidationError, match="unexpected files"):
        validate_assets(manifest, tmp_path, require_all=True, strict=True)

    (tmp_path / filename).unlink()
    with pytest.raises(ManifestValidationError, match="missing 1 expected files"):
        validate_assets(manifest, tmp_path, require_all=True, strict=False)
