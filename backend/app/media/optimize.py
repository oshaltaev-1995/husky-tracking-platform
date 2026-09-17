from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.media.validate import DEFAULT_MANIFEST, REPOSITORY_ROOT
from app.media.validation import load_manifest, validate_assets, validate_manifest

DEFAULT_SOURCE_DIRECTORY = REPOSITORY_ROOT / "media" / "dogs-source"
DEFAULT_OUTPUT_DIRECTORY = REPOSITORY_ROOT / "media" / "dogs-optimized"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Re-encode already-valid target-size WebPs with cwebp into a new directory."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--source-directory", type=Path, default=DEFAULT_SOURCE_DIRECTORY
    )
    parser.add_argument(
        "--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY
    )
    parser.add_argument("--quality", type=int, default=86, choices=range(1, 101))
    args = parser.parse_args()

    cwebp = shutil.which("cwebp")
    if cwebp is None:
        parser.exit(1, "cwebp is required but was not found on PATH.\n")
    source = args.source_directory.resolve()
    output = args.output_directory.resolve()
    if source == output:
        parser.exit(1, "Source and output directories must differ.\n")
    if output.exists() and any(
        path for path in output.iterdir() if not path.name.startswith(".")
    ):
        parser.exit(1, f"Output directory must be empty: {output}\n")

    manifest = load_manifest(args.manifest)
    validate_manifest(manifest)
    validate_assets(manifest, source, require_all=True, strict=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    version = subprocess.run(
        [cwebp, "-version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="dog-media-", dir=output.parent) as temp:
        temporary = Path(temp)
        for dog in manifest.dogs:
            subprocess.run(
                [
                    cwebp,
                    "-preset",
                    "photo",
                    "-q",
                    str(args.quality),
                    "-m",
                    "6",
                    "-sharp_yuv",
                    "-metadata",
                    "none",
                    str(source / dog.target_filename),
                    "-o",
                    str(temporary / dog.target_filename),
                ],
                check=True,
                capture_output=True,
            )
        report = validate_assets(manifest, temporary, require_all=True, strict=True)
        output.mkdir(parents=True, exist_ok=True)
        for asset in temporary.iterdir():
            asset.replace(output / asset.name)

    print(
        f"Optimized {report.found_files} assets with cwebp {version} at quality "
        f"{args.quality}; KB min/median/max {report.minimum_size_kb:.1f}/"
        f"{report.median_size_kb:.1f}/{report.maximum_size_kb:.1f}."
    )


if __name__ == "__main__":
    main()
