"""Real ECE-YOLO inference smoke test (skipped when assets are absent)."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from app.algorithms.ece_yolo.detector import EceYoloDetector
from app.algorithms.registry import load_model_specs
from app.core.config import get_settings
from PIL import Image

SAMPLE = Path(
    r"D:\yolo11（2）\VisDrone VisDrone\VisDrone2019-DET-val\images\0000001_02999_d_0000005.jpg"
)


@pytest.mark.skipif(not SAMPLE.is_file(), reason="VisDrone sample image not available")
def test_real_ece_yolo_cpu_inference():
    specs, _ = load_model_specs(get_settings().models_config)
    spec = replace(specs["ece-yolo"], device="cpu")

    detector = EceYoloDetector(spec)
    detector.load()
    try:
        assert detector.loaded is True
        image = Image.open(SAMPLE).convert("RGB")
        image_bgr = np.asarray(image)[:, :, ::-1].copy()

        detections = detector.predict(image_bgr, conf=0.25, iou=0.7)

        assert len(detections) > 0
        assert all(0.0 <= item.confidence <= 1.0 for item in detections)
        assert all(item.class_name for item in detections)
        assert all(item.bbox[2] > item.bbox[0] and item.bbox[3] > item.bbox[1] for item in detections)
    finally:
        detector.unload()
