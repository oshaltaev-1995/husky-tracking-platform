from __future__ import annotations

import argparse
from pathlib import Path

from app.media.validation import (
    ManifestValidationError,
    load_manifest,
    validate_assets,
    validate_manifest,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "docs" / "dog-media-manifest.json"
DEFAULT_ASSET_DIRECTORY = REPOSITORY_ROOT / "frontend" / "public" / "media" / "dogs"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the canonical dog-media manifest and optional WebP assets."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--asset-directory", type=Path, default=DEFAULT_ASSET_DIRECTORY)
    parser.add_argument(
        "--check-assets",
        action="store_true",
        help="Validate any canonical assets currently present.",
    )
    parser.add_argument(
        "--require-assets",
        action="store_true",
        help="Require every manifest asset; this is the P10B acceptance mode.",
    )
    parser.add_argument(
        "--strict-assets",
        action="store_true",
        help="Reject non-hidden files not listed by the manifest.",
    )
    args = parser.parse_args()

    try:
        manifest = load_manifest(args.manifest)
        validate_manifest(manifest)
        print(
            f"Manifest {manifest.manifest_version} is valid: "
            f"{len(manifest.dogs)} canonical dogs."
        )
        if args.check_assets or args.require_assets or args.strict_assets:
            report = validate_assets(
                manifest,
                args.asset_directory,
                require_all=args.require_assets,
                strict=args.strict_assets,
            )
            print(
                f"Assets valid: {report.found_files}/{report.expected_files}; "
                f"size KB min/median/max {report.minimum_size_kb:.1f}/"
                f"{report.median_size_kb:.1f}/{report.maximum_size_kb:.1f}."
            )
    except ManifestValidationError as exc:
        parser.exit(1, f"Dog media validation failed:\n{exc}\n")


if __name__ == "__main__":
    main()
