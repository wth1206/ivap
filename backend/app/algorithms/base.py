"""Detector abstraction and shared data types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


@dataclass(frozen=True)
class Detection:
    """One detected object in original-image pixel coordinates."""

    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2


class BaseDetector(ABC):
    """Interface implemented by every model adapter."""

    key: str
    display_name: str
    is_mock: bool = False

    @property
    @abstractmethod
    def loaded(self) -> bool:
        """Whether the model weights are resident."""

    @property
    @abstractmethod
    def device(self) -> str:
        """Device string, e.g. ``cpu`` or ``cuda:0``."""

    @abstractmethod
    def load(self) -> None:
        """Load weights.  Must be idempotent."""

    @abstractmethod
    def predict(self, image: np.ndarray, conf: float, iou: float) -> List[Detection]:
        """Run inference on a BGR ``uint8`` HWC image."""

    def unload(self) -> None:
        """Release model resources (best effort)."""
        return None

    def info(self) -> Dict[str, object]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "loaded": self.loaded,
            "device": self.device,
            "is_mock": self.is_mock,
        }
