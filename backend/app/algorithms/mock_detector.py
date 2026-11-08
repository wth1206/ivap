"""Deterministic mock detector, clearly marked with ``is_mock=True``."""

from typing import List

import numpy as np

from app.algorithms.base import BaseDetector, Detection


class MockDetector(BaseDetector):
    is_mock = True

    def __init__(self, spec) -> None:
        self.spec = spec
        self.key = spec.key
        self.display_name = spec.display_name
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def device(self) -> str:
        return "cpu"

    def load(self) -> None:
        self._loaded = True

    def predict(self, image: np.ndarray, conf: float, iou: float) -> List[Detection]:
        if image is None or image.size == 0:
            return []
        height, width = image.shape[:2]
        boxes = [
            (0.10, 0.10, 0.28, 0.30, 0.90),
            (0.42, 0.38, 0.58, 0.56, 0.75),
            (0.70, 0.62, 0.88, 0.84, 0.60),
        ]
        detections = []
        for x1, y1, x2, y2, score in boxes:
            detections.append(
                Detection(
                    class_id=0,
                    class_name="mock_object",
                    confidence=score,
                    bbox=(
                        int(x1 * width),
                        int(y1 * height),
                        int(x2 * width),
                        int(y2 * height),
                    ),
                )
            )
        return detections
