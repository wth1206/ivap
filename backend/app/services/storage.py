"""File-system storage for images and documents.

Only relative POSIX paths are stored in the database; the absolute root is
resolved at runtime.  This keeps the DB portable between local dev and Docker.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from PIL import Image

from app.core.exceptions import AppError
from app.utils.image import sha256_bytes

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredImage:
    relative_path: str
    absolute_path: Path
    sha256: str
    width: int
    height: int


class StorageService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative_path: str) -> Path:
        """Resolve a relative path and reject traversal outside the root."""
        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise AppError("INVALID_PATH", "非法的文件路径", 400)
        return candidate

    def save_image(self, image: Image.Image, data: bytes, original_name: str) -> StoredImage:
        now = datetime.utcnow()
        relative = (
            Path("images") / f"{now:%Y}" / f"{now:%m}" / f"{uuid4().hex}.jpg"
        )
        absolute = self.resolve(relative.as_posix())
        absolute.parent.mkdir(parents=True, exist_ok=True)
        image.save(absolute, format="JPEG", quality=95, subsampling=0)
        return StoredImage(
            relative_path=relative.as_posix(),
            absolute_path=absolute,
            sha256=sha256_bytes(data),
            width=image.width,
            height=image.height,
        )

    def save_result_image(self, task_id: str, image: Image.Image) -> str:
        """Save an annotated result image and return its relative path."""
        now = datetime.utcnow()
        relative = Path("results") / f"{now:%Y}" / f"{now:%m}" / f"{task_id}.jpg"
        absolute = self.resolve(relative.as_posix())
        absolute.parent.mkdir(parents=True, exist_ok=True)
        image.save(absolute, format="JPEG", quality=92, subsampling=0)
        return relative.as_posix()

    def save_document(self, document_id: str, data: bytes, extension: str) -> str:
        """Save an uploaded knowledge document and return its relative path."""
        suffix = extension if extension.startswith(".") else f".{extension}"
        relative = Path("documents") / document_id / f"original{suffix}"
        absolute = self.resolve(relative.as_posix())
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_bytes(data)
        return relative.as_posix()

    def delete(self, relative_path: Optional[str]) -> bool:
        if not relative_path:
            return False
        try:
            target = self.resolve(relative_path)
        except AppError:
            logger.warning("Refusing to delete path outside upload root: %s", relative_path)
            return False
        try:
            if target.is_file():
                target.unlink()
                return True
        except OSError as exc:
            logger.warning("Failed to delete %s: %s", target, exc)
        return False

    @staticmethod
    def url_for(relative_path: str) -> str:
        return f"/static/{relative_path}"
