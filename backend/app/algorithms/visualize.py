"""Draw detection boxes on an image with PIL (supports Unicode labels)."""

from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from app.algorithms.base import Detection

_PALETTE = [
    "#e63946",
    "#2a9d8f",
    "#e9c46a",
    "#457b9d",
    "#f4a261",
    "#9b5de5",
    "#00b4d8",
    "#f15bb5",
    "#8ac926",
    "#ff924c",
]
_FONT_CACHE: Optional[ImageFont.ImageFont] = None


def _load_font(size: int = 16) -> ImageFont.ImageFont:
    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE
    for candidate in (
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ):
        if Path(candidate).is_file():
            try:
                _FONT_CACHE = ImageFont.truetype(candidate, size)
                return _FONT_CACHE
            except OSError:
                continue
    _FONT_CACHE = ImageFont.load_default()
    return _FONT_CACHE


def draw_detections(image: Image.Image, detections: List[Detection]) -> Image.Image:
    """Return a copy of ``image`` with boxes and labels drawn."""
    canvas = image.copy()
    if not detections:
        return canvas

    draw = ImageDraw.Draw(canvas)
    font = _load_font(16)

    for det in detections:
        color = _PALETTE[det.class_id % len(_PALETTE)]
        x1, y1, x2, y2 = det.bbox
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        label = f"{det.class_name} {det.confidence:.2f}"
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        text_w, text_h = right - left, bottom - top
        label_y = y1 - text_h - 6
        if label_y < 0:
            label_y = y1 + 2
        draw.rectangle(
            [x1, label_y, x1 + text_w + 8, label_y + text_h + 4],
            fill=color,
        )
        draw.text((x1 + 4, label_y + 2), label, fill="white", font=font)

    return canvas
