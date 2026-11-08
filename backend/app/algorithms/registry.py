"""Model registry: parse ``models.yaml`` and build detector adapters."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from app.core.config import PROJECT_ROOT


class ModelConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelSpec:
    key: str
    display_name: str
    adapter: str
    weights: Optional[Path]
    device: str
    imgsz: int
    conf: float
    iou: float
    class_names: Optional[List[str]]
    max_det: int

    @property
    def is_mock(self) -> bool:
        return self.adapter == "mock"


def _resolve_weights(raw: Optional[str]) -> Optional[Path]:
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def load_model_specs(config_path: Path) -> Tuple[Dict[str, ModelSpec], str]:
    """Parse the YAML registry and return ``(specs, default_key)``."""
    config_path = Path(config_path)
    if not config_path.is_file():
        raise ModelConfigError(f"models config not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    models = raw.get("models")
    if not isinstance(models, dict) or not models:
        raise ModelConfigError("models.yaml must contain a non-empty 'models' mapping")

    specs: Dict[str, ModelSpec] = {}
    for key, item in models.items():
        if not isinstance(item, dict):
            raise ModelConfigError(f"model {key!r} must be a mapping")
        adapter = str(item.get("adapter", "ultralytics"))
        if adapter not in {"ece_yolo", "mock", "ultralytics"}:
            raise ModelConfigError(f"unsupported adapter {adapter!r} for model {key!r}")
        specs[str(key)] = ModelSpec(
            key=str(key),
            display_name=str(item.get("display_name", key)),
            adapter=adapter,
            weights=_resolve_weights(item.get("weights")),
            device=str(item.get("device", "auto")),
            imgsz=int(item.get("imgsz", 640)),
            conf=float(item.get("conf", 0.25)),
            iou=float(item.get("iou", 0.7)),
            class_names=item.get("class_names"),
            max_det=int(item.get("max_det", 300)),
        )

    default_key = str(raw.get("default") or next(iter(specs)))
    if default_key not in specs:
        raise ModelConfigError(f"default model {default_key!r} is not in models")
    return specs, default_key


def build_detector(spec: ModelSpec):
    """Instantiate (but do not load) the adapter for ``spec``."""
    if spec.adapter == "mock":
        from app.algorithms.mock_detector import MockDetector

        return MockDetector(spec)
    if spec.adapter == "ece_yolo":
        from app.algorithms.ece_yolo.detector import EceYoloDetector

        return EceYoloDetector(spec)
    raise ModelConfigError(f"adapter {spec.adapter!r} is not implemented")
