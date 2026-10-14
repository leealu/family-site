#!/usr/bin/env python3
"""Build a complete deployment copy and ZIP from outputs/site."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "outputs" / "site"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
EXCLUDED_DIRECTORIES = {"data", "__pycache__", ".git"}
EXCLUDED_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".pyc", ".pyo", ".pyd"}


def _is_excluded(relative_path: Path) -> bool:
    if any(part in EXCLUDED_DIRECTORIES for part in relative_path.parts):
        return True
    if any(part == ".env" or (part.startswith(".env.") and part != ".env.example") for part in relative_path.parts):
        return True
    return relative_path.suffix.lower() in EXCLUDED_SUFFIXES


def _copy_deployable_files(source: Path, destination: Path) -> None:
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
            target = destination / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)


def build_deployment_package(
    source: Path = DEFAULT_SOURCE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    name: str = "family-site",
) -> tuple[Path, Path]:
    """Replace the generated deployment folder and ZIP with a full source copy."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or name in {".", ".."}:
        raise ValueError("Package name may contain only letters, numbers, dots, underscores, and hyphens.")

    source = Path(source).resolve()
    output_dir = Path(output_dir).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Deployment source directory not found: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)

    package_dir = output_dir / name
    archive_path = output_dir / f"{name}.zip"
    if package_dir == source or package_dir in source.parents or source in package_dir.parents:
        raise ValueError("The generated package and canonical source must be separate directories.")
    if package_dir.parent != output_dir or archive_path.parent != output_dir:
        raise ValueError("Generated outputs must be direct children of the output directory.")
    if package_dir.is_symlink() or archive_path.is_symlink():
        raise ValueError("Refusing to replace a symbolic link in the output directory.")
    if package_dir.exists() and not package_dir.is_dir():
        raise ValueError(f"Package output is not a directory: {package_dir}")
    if archive_path.exists() and not archive_path.is_file():
        raise ValueError(f"Archive output is not a file: {archive_path}")

    with tempfile.TemporaryDirectory(prefix=f".{name}-build-", dir=output_dir) as temporary:
        temporary_root = Path(temporary)
        staged_folder = temporary_root / name
        staged_folder.mkdir()
        _copy_deployable_files(source, staged_folder)
        staged_archive = temporary_root / f"{name}.zip"
        with zipfile.ZipFile(staged_archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for file_path in sorted(path for path in staged_folder.rglob("*") if path.is_file()):
                bundle.write(file_path, file_path.relative_to(staged_folder).as_posix())

        if package_dir.exists():
            shutil.rmtree(package_dir)
        if archive_path.exists():
            archive_path.unlink()
        shutil.copytree(staged_folder, package_dir)
        shutil.copy2(staged_archive, archive_path)

    return package_dir, archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a complete deployment package from outputs/site.")
    parser.add_argument("--name", default="family-site", help="Output folder and ZIP base name (default: family-site).")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Canonical website source directory.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for generated outputs.")
    args = parser.parse_args()
    folder, archive = build_deployment_package(args.source, args.output_dir, args.name)
    count = sum(1 for path in folder.rglob("*") if path.is_file())
    print(f"Deployment folder: {folder}")
    print(f"ZIP archive: {archive} ({archive.stat().st_size:,} bytes)")
    print(f"Files copied from canonical source: {count}")


if __name__ == "__main__":
    main()

