"""Process-wide model manager.

Loads each configured model at most once, serialises GPU inference and exposes
health/model-list information to the API.
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.algorithms.base import BaseDetector, Detection
from app.algorithms.registry import ModelSpec, build_detector, load_model_specs
from app.core.config import Settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


class ModelManager:
    def __init__(self) -> None:
        self._settings: Optional[Settings] = None
        self._configured = False
        self._mode = "real"
        self._specs: Dict[str, ModelSpec] = {}
        self._default_key: Optional[str] = None
        self._config_error: Optional[str] = None
        self._detectors: Dict[str, BaseDetector] = {}
        self._load_lock = threading.RLock()
        self._infer_lock = threading.Lock()

    # ------------------------------------------------------------------
    # configuration / lifecycle
    # ------------------------------------------------------------------
    def configure(self, settings: Settings) -> None:
        self.shutdown()
        self._settings = settings
        self._mode = settings.detector_mode
        self._configured = True
        self._config_error = None
        self._specs = {}
        self._default_key = None

        try:
            specs, default_key = load_model_specs(settings.models_config)
            if settings.default_model and settings.default_model in specs:
                default_key = settings.default_model
            self._specs = specs
            self._default_key = default_key
        except Exception as exc:
            self._config_error = str(exc)
            logger.warning("Model config unavailable: %s", exc)

        if self._mode == "mock":
            if "mock" not in self._specs:
                self._specs["mock"] = ModelSpec(
                    key="mock",
                    display_name="Mock Detector (开发用)",
                    adapter="mock",
                    weights=None,
                    device="cpu",
                    imgsz=640,
                    conf=0.25,
                    iou=0.7,
                    class_names=["mock_object"],
                    max_det=100,
                )
            self._default_key = "mock"

    def preload(self) -> None:
        if not self._settings or not self._settings.model_preload:
            return
        if not self._specs or self._default_key is None:
            return
        try:
            self.get(self._default_key)
        except AppError as exc:
            logger.warning("Model preload skipped: %s", exc.message)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Model preload failed: %s", exc)

    def shutdown(self) -> None:
        for detector in self._detectors.values():
            try:
                detector.unload()
            except Exception:  # pragma: no cover - defensive
                logger.exception("Failed to unload detector %s", detector.key)
        self._detectors.clear()
        self._configured = False

    # ------------------------------------------------------------------
    # lookup
    # ------------------------------------------------------------------
    @property
    def default_key(self) -> Optional[str]:
        return self._default_key

    def _default_spec(self) -> Optional[ModelSpec]:
        if self._mode == "mock" and "mock" in self._specs:
            return self._specs["mock"]
        if self._default_key:
            return self._specs.get(self._default_key)
        return None

    def get_spec(self, name: Optional[str] = None) -> ModelSpec:
        if not self._configured:
            raise AppError("MODEL_CONFIG_NOT_FOUND", "模型管理器尚未初始化", 503)
        if not self._specs:
            raise AppError(
                "MODEL_CONFIG_NOT_FOUND",
                "模型配置不可用，请检查 MODELS_CONFIG",
                503,
                {"reason": self._config_error},
            )

        if self._mode == "mock":
            mock = self._specs.get("mock")
            if mock is not None:
                return mock

        candidate = name or self._default_key
        if candidate and candidate in self._specs:
            return self._specs[candidate]

        if candidate:
            lowered = candidate.lower()
            for spec in self._specs.values():
                if spec.display_name.lower() == lowered:
                    return spec
        raise AppError(
            "MODEL_NOT_FOUND",
            "未找到指定的模型",
            404,
            {"model": name, "available": sorted(self._specs)},
        )

    def ensure_available(self, spec: ModelSpec) -> None:
        if spec.adapter == "mock":
            return
        if spec.weights is None or not spec.weights.is_file():
            raise AppError(
                "MODEL_WEIGHTS_NOT_FOUND",
                "模型权重不存在",
                503,
                {"model": spec.key, "weights": str(spec.weights)},
            )

    def get(self, name: Optional[str] = None) -> BaseDetector:
        spec = self.get_spec(name)
        self.ensure_available(spec)

        with self._load_lock:
            detector = self._detectors.get(spec.key)
            if detector is not None and detector.loaded:
                return detector

            detector = build_detector(spec)
            try:
                detector.load()
            except AppError:
                raise
            except Exception as exc:
                logger.exception("Failed to load model %s", spec.key)
                raise AppError(
                    "MODEL_LOAD_FAILED",
                    "模型加载失败",
                    503,
                    {"model": spec.key, "reason": str(exc)[:300]},
                ) from exc
            self._detectors[spec.key] = detector
            return detector

    # ------------------------------------------------------------------
    # inference
    # ------------------------------------------------------------------
    def predict_sync(
        self,
        name: Optional[str],
        image: np.ndarray,
        conf: float,
        iou: float,
    ) -> Tuple[List[Detection], int]:
        detector = self.get(name)
        with self._infer_lock:
            started = time.perf_counter()
            detections = detector.predict(image, conf, iou)
            elapsed_ms = int(round((time.perf_counter() - started) * 1000))
        logger.info(
            "model=%s device=%s objects=%d inference=%dms",
            detector.key,
            detector.device,
            len(detections),
            elapsed_ms,
        )
        return detections, elapsed_ms

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    def health(self) -> Dict[str, object]:
        if not self._configured:
            return {
                "status": "not_configured",
                "model": None,
                "loaded": False,
                "device": None,
                "mock": False,
                "detail": "模型管理器未初始化",
            }

        spec = self._default_spec()
        if spec is None:
            return {
                "status": "unavailable",
                "model": None,
                "loaded": False,
                "device": None,
                "mock": self._mode == "mock",
                "detail": self._config_error or "没有可用模型",
            }

        available = spec.is_mock or (spec.weights is not None and spec.weights.is_file())
        detector = self._detectors.get(spec.key)
        return {
            "status": "ok" if available else "unavailable",
            "model": spec.display_name,
            "loaded": bool(detector and detector.loaded),
            "device": detector.device if detector else (spec.device if spec.device != "auto" else "auto"),
            "mock": spec.is_mock,
            "detail": None if available else f"权重不存在: {spec.weights}",
        }

    def list_models(self) -> List[Dict[str, object]]:
        default_spec = self._default_spec()
        rows = []
        for spec in self._specs.values():
            detector = self._detectors.get(spec.key)
            available = spec.is_mock or (spec.weights is not None and spec.weights.is_file())
            rows.append(
                {
                    "key": spec.key,
                    "display_name": spec.display_name,
                    "adapter": spec.adapter,
                    "available": available,
                    "loaded": bool(detector and detector.loaded),
                    "device": detector.device if detector else spec.device,
                    "imgsz": spec.imgsz,
                    "conf": spec.conf,
                    "iou": spec.iou,
                    "is_mock": spec.is_mock,
                    "default": bool(default_spec and spec.key == default_spec.key),
                }
            )
        return rows


_manager = ModelManager()


def get_model_manager() -> ModelManager:
    return _manager
