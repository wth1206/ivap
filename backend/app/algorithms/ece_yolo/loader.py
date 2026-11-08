"""Load an ECE-YOLO checkpoint with its custom modules."""

import logging
from pathlib import Path
from typing import Any

from app.algorithms.ece_yolo.mmcv_shim import install_mmcv_shim
from app.algorithms.ece_yolo.modules import register_ece_modules
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


def load_ece_yolo(weights: Path, device: str) -> Any:
    """Return a loaded Ultralytics ``YOLO`` object for ``weights``."""
    weights = Path(weights)
    if not weights.is_file():
        raise AppError(
            "MODEL_WEIGHTS_NOT_FOUND",
            "未找到 ECE-YOLO 权重文件",
            503,
            {"weights": str(weights)},
        )

    install_mmcv_shim()
    register_ece_modules()

    from ultralytics import YOLO

    logger.info("Loading ECE-YOLO weights %s on %s", weights, device)
    model = YOLO(str(weights))
    if device and device != "auto":
        model.to(device)
    model.model.eval()
    return model
