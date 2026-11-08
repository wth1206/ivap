"""Image validation and normalisation."""

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import AppError

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_FORMATS = {"JPEG", "PNG"}
_MAGIC_JPEG = b"\xff\xd8\xff"
_MAGIC_PNG = b"\x89PNG\r\n\x1a\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_magic(data: bytes) -> None:
    if not (data.startswith(_MAGIC_JPEG) or data.startswith(_MAGIC_PNG)):
        raise AppError("INVALID_IMAGE", "文件内容不是有效的 JPG/PNG 图片", 400)


def validate_image_bytes(data: bytes, filename: str, max_mb: int) -> Tuple[Image.Image, str]:
    """Validate an uploaded image and return ``(RGB image, extension)``.

    Raises ``AppError`` with a stable code so the API can return a useful
    message without leaking internals.
    """
    if not data:
        raise AppError("INVALID_IMAGE", "上传的图片为空", 400)
    if len(data) > max_mb * 1024 * 1024:
        raise AppError(
            "FILE_TOO_LARGE",
            f"图片超过 {max_mb} MB 限制",
            413,
            {"max_mb": max_mb, "actual_bytes": len(data)},
        )

    extension = Path(filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise AppError(
            "INVALID_FILE_TYPE",
            "仅支持 JPG、JPEG、PNG 图片",
            400,
            {"extension": extension},
        )

    _check_magic(data)

    try:
        with Image.open(BytesIO(data)) as probe:
            if probe.format not in ALLOWED_FORMATS:
                raise AppError("INVALID_IMAGE", "图片格式不受支持", 400)
            probe.verify()

        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGB")
            width, height = image.size
            if width < 1 or height < 1:
                raise AppError("INVALID_IMAGE", "图片尺寸无效", 400)
            if width * height > 120_000_000:
                raise AppError("INVALID_IMAGE", "图片像素过大，请缩小后再上传", 400)
            return image.copy(), extension
    except AppError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AppError(
            "INVALID_IMAGE", "图片无法解码，请确认文件未损坏", 400
        ) from exc
