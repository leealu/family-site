#!/usr/bin/env python3
"""Build a deployment ZIP from the canonical outputs/family-site folder."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "outputs" / "family-site"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
EXCLUDED_DIRECTORIES = {"data", "__pycache__", ".git"}
EXCLUDED_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".pyc", ".pyo", ".pyd"}


def _is_excluded(relative_path: Path) -> bool:
    if any(part in EXCLUDED_DIRECTORIES for part in relative_path.parts):
        return True
    if any(part == ".env" or (part.startswith(".env.") and part != ".env.example") for part in relative_path.parts):
        return True
    return relative_path.suffix.lower() in EXCLUDED_SUFFIXES


def _add_deployable_files(source: Path, bundle: zipfile.ZipFile) -> int:
    count = 0
    for root, directories, filenames in os.walk(source, followlinks=False):
        current = Path(root)
        relative_directory = current.relative_to(source)
        directories[:] = [
            name
            for name in directories
            if not _is_excluded(relative_directory / name)
            and not (current / name).is_symlink()
        ]
        for filename in filenames:
            original = current / filename
            relative_path = original.relative_to(source)
            if _is_excluded(relative_path) or original.is_symlink():
                continue
            bundle.write(original, relative_path.as_posix())
            count += 1
    return count


def build_deployment_package(
    source: Path = DEFAULT_SOURCE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    name: str = "family-site",
) -> tuple[Path, Path]:
    """Build a ZIP from the canonical folder without modifying or copying it."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or name in {".", ".."}:
        raise ValueError("Package name may contain only letters, numbers, dots, underscores, and hyphens.")

    source = Path(source)
    if source.is_symlink():
        raise ValueError("Refusing to read a symbolic link as the canonical deployment folder.")
    source = source.resolve()
    output_dir = Path(output_dir).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Deployment source directory not found: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)

    archive_path = output_dir / f"{name}.zip"
    if source.parent != output_dir or archive_path.parent != output_dir:
        raise ValueError("The canonical folder and generated ZIP must be direct children of the output directory.")
    if archive_path.is_symlink():
        raise ValueError("Refusing to read or replace a symbolic link in the output directory.")
    if not source.is_dir():
        raise FileNotFoundError(f"Canonical deployment directory not found: {source}")
    if archive_path.exists() and not archive_path.is_file():
        raise ValueError(f"Archive output is not a file: {archive_path}")

    with tempfile.TemporaryDirectory(prefix=f".{name}-build-", dir=output_dir) as temporary:
        temporary_root = Path(temporary)
        staged_archive = temporary_root / f"{name}.zip"
        with zipfile.ZipFile(staged_archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            count = _add_deployable_files(source, bundle)
        if archive_path.exists():
            archive_path.unlink()
        shutil.copy2(staged_archive, archive_path)

    return source, archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deployment ZIP from outputs/family-site.")
    parser.add_argument("--name", default="family-site", help="ZIP base name (default: family-site).")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Canonical deployment directory.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for generated outputs.")
    args = parser.parse_args()
    folder, archive = build_deployment_package(args.source, args.output_dir, args.name)
    with zipfile.ZipFile(archive) as bundle:
        count = len(bundle.namelist())
    print(f"Canonical deployment folder: {folder}")
    print(f"ZIP archive: {archive} ({archive.stat().st_size:,} bytes)")
    print(f"Files packaged from canonical folder: {count}")


if __name__ == "__main__":
    main()

