"""Create a clean, reproducible IVAP source archive.

Usage:
    python scripts/archive_project.py
    python scripts/archive_project.py --no-weights
"""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = ROOT / "archive"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".mysql",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    ".vite",
    "uploads",
    "vector_db",
    "logs",
    "data",
    "archive",
}
EXCLUDED_FILES = {".env", ".env.docker", ".DS_Store", "Thumbs.db"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".db", ".sqlite3"}


def is_excluded(relative: Path, include_weights: bool) -> bool:
    parts = set(relative.parts)
    if parts & EXCLUDED_DIRS:
        return True
    if relative.name in EXCLUDED_FILES:
        return True
    if relative.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if not include_weights and relative.suffix.lower() in {".pt", ".pth", ".onnx", ".engine"}:
        return True
    return False


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-weights", action="store_true", help="do not include best.pt")
    args = parser.parse_args()

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    target = ARCHIVE_DIR / f"IVAP-source-{stamp}.zip"
    manifest = ARCHIVE_DIR / f"IVAP-source-{stamp}-manifest.txt"

    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if is_excluded(relative, include_weights=not args.no_weights):
            continue
        files.append(path)
    files.sort(key=lambda item: item.relative_to(ROOT).as_posix())

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            zf.write(path, path.relative_to(ROOT).as_posix())

    lines = [
        f"IVAP source archive: {target.name}",
        f"created: {datetime.now().isoformat(timespec='seconds')}",
        f"files: {len(files)}",
        f"bytes: {target.stat().st_size}",
        "",
        "path\tsize_bytes",
    ]
    for path in files:
        lines.append(f"{path.relative_to(ROOT).as_posix()}\t{path.stat().st_size}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    digest = sha256(target)
    checksum = ARCHIVE_DIR / f"IVAP-source-{stamp}.sha256.txt"
    checksum.write_text(f"{digest}  {target.name}\n", encoding="utf-8")

    print(f"archive={target}")
    print(f"files={len(files)} size_mb={target.stat().st_size / 1024 / 1024:.2f}")
    print(f"sha256={digest}")
    print(f"manifest={manifest}")
    print(f"checksum={checksum}")


if __name__ == "__main__":
    main()
