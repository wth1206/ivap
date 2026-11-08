"""ECE-YOLO detector adapter."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.algorithms.base import BaseDetector, Detection
from app.algorithms.ece_yolo.loader import load_ece_yolo
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


def resolve_device(value: str) -> str:
    if value and value != "auto":
        return value
    try:
        import torch

        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


class EceYoloDetector(BaseDetector):
    is_mock = False

    def __init__(self, spec) -> None:  # spec: ModelSpec (avoid import cycle)
        self.spec = spec
        self.key = spec.key
        self.display_name = spec.display_name
        self._model = None
        self._device = resolve_device(spec.device)
        self._names: Dict[int, str] = {}

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        return self._device

    def load(self) -> None:
        if self._model is not None:
            return
        weights: Optional[Path] = self.spec.weights
        if weights is None:
            raise AppError("MODEL_WEIGHTS_NOT_FOUND", "模型未配置权重路径", 503)
        self._device = resolve_device(self.spec.device)
        self._model = load_ece_yolo(weights, self._device)
        self._names = dict(getattr(self._model, "names", {}) or {})
        logger.info(
            "ECE-YOLO loaded: %s on %s (%d classes)",
            self.display_name,
            self._device,
            len(self._names),
        )
        self.warmup()

    def warmup(self) -> None:
        """Run one dummy inference so the first real request is not penalised."""
        if self._model is None:
            return
        dummy = np.zeros((self.spec.imgsz, self.spec.imgsz, 3), dtype=np.uint8)
        try:
            self._model.predict(
                source=dummy,
                imgsz=self.spec.imgsz,
                conf=self.spec.conf,
                iou=self.spec.iou,
                device=self._device,
                verbose=False,
                max_det=10,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("ECE-YOLO warmup failed: %s", exc)

    def predict(self, image: np.ndarray, conf: float, iou: float) -> List[Detection]:
        if self._model is None:
            raise AppError("MODEL_NOT_READY", "模型尚未加载", 503)
        if image is None or image.size == 0:
            return []

        height, width = image.shape[:2]
        results = self._model.predict(
            source=np.ascontiguousarray(image),
            imgsz=self.spec.imgsz,
            conf=conf,
            iou=iou,
            device=self._device,
            verbose=False,
            max_det=self.spec.max_det,
        )
        if not results:
            return []

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return []

        xyxy = boxes.xyxy.detach().cpu().numpy()
        scores = boxes.conf.detach().cpu().numpy()
        class_ids = boxes.cls.detach().cpu().numpy()

        detections: List[Detection] = []
        for (x1, y1, x2, y2), score, class_id in zip(xyxy, scores, class_ids):
            left = max(0, min(width - 1, int(round(float(x1)))))
            top = max(0, min(height - 1, int(round(float(y1)))))
            right = max(0, min(width - 1, int(round(float(x2)))))
            bottom = max(0, min(height - 1, int(round(float(y2)))))
            if right <= left or bottom <= top:
                continue
            cid = int(class_id)
            detections.append(
                Detection(
                    class_id=cid,
                    class_name=self._names.get(cid, str(cid)),
                    confidence=float(score),
                    bbox=(left, top, right, bottom),
                )
            )

        detections.sort(key=lambda item: item.confidence, reverse=True)
        return detections

    def unload(self) -> None:
        self._model = None
        self._names = {}
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def info(self) -> Dict[str, object]:
        payload = super().info()
        payload.update({"imgsz": self.spec.imgsz, "classes": len(self._names)})
        return payload
