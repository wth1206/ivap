"""Detection statistics computed in Python (the LLM only explains them).

All numbers passed to the report prompt come from this module; the model is
not allowed to count objects or invent metrics.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

GRID_LABELS = (
    ("左上", "上中", "右上"),
    ("左中", "中心", "右中"),
    ("左下", "下中", "右下"),
)


@dataclass(frozen=True)
class BoxRecord:
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]


def _density_level(per_megapixel: float) -> str:
    if per_megapixel < 5:
        return "稀疏"
    if per_megapixel < 20:
        return "中等"
    if per_megapixel < 50:
        return "密集"
    return "极密集"


def _iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    return inter / (area_a + area_b - inter)


def compute_facts(
    width: int,
    height: int,
    boxes: Sequence[BoxRecord],
) -> Dict[str, object]:
    """Compute class, density, spatial, size, confidence and overlap facts."""
    safe_w = max(1, int(width))
    safe_h = max(1, int(height))
    total = len(boxes)
    megapixels = (safe_w * safe_h) / 1_000_000
    density = total / megapixels if megapixels > 0 else 0.0

    centers = [
        ((box.bbox[0] + box.bbox[2]) / 2.0, (box.bbox[1] + box.bbox[3]) / 2.0)
        for box in boxes
    ]

    grid_counts = {label: 0 for row in GRID_LABELS for label in row}
    for cx, cy in centers:
        col = min(2, max(0, int(cx / safe_w * 3)))
        row = min(2, max(0, int(cy / safe_h * 3)))
        grid_counts[GRID_LABELS[row][col]] += 1
    grid_percentages = {
        label: round((count / total * 100.0) if total else 0.0, 2)
        for label, count in grid_counts.items()
    }
    dominant = max(grid_counts, key=grid_counts.get) if total else "无目标"

    if len(centers) >= 2:
        points = np.asarray(centers[:300], dtype=np.float32)
        deltas = points[:, None, :] - points[None, :, :]
        distances = np.linalg.norm(deltas, axis=2)
        np.fill_diagonal(distances, np.inf)
        nearest = distances.min(axis=1)
        nearest_mean = float(nearest.mean())
        nearest_median = float(np.median(nearest))
        diagonal = float(np.hypot(safe_w, safe_h))
        nearest_percent = nearest_mean / diagonal * 100.0 if diagonal else 0.0
        nearest_sampled = int(len(points))
    else:
        nearest_mean = nearest_median = nearest_percent = 0.0
        nearest_sampled = len(centers)

    margin_x = safe_w * 0.05
    margin_y = safe_h * 0.05
    edge_count = 0
    for box in boxes:
        x1, y1, x2, y2 = box.bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        if (
            cx <= margin_x
            or cx >= safe_w - margin_x
            or cy <= margin_y
            or cy >= safe_h - margin_y
            or x1 <= 1
            or y1 <= 1
            or x2 >= safe_w - 2
            or y2 >= safe_h - 2
        ):
            edge_count += 1

    size_counts = {"small": 0, "medium": 0, "large": 0}
    for box in boxes:
        x1, y1, x2, y2 = box.bbox
        ratio = max(0, (x2 - x1) * (y2 - y1)) / (safe_w * safe_h)
        if ratio < 0.001:
            size_counts["small"] += 1
        elif ratio <= 0.01:
            size_counts["medium"] += 1
        else:
            size_counts["large"] += 1
    size_percentages = {
        key: round((value / total * 100.0) if total else 0.0, 2)
        for key, value in size_counts.items()
    }

    confidences = [box.confidence for box in boxes]
    if confidences:
        conf_mean = float(np.mean(confidences))
        conf_min = float(np.min(confidences))
        conf_max = float(np.max(confidences))
        low_conf = sum(1 for value in confidences if value < 0.4)
        high_conf = sum(1 for value in confidences if value >= 0.7)
    else:
        conf_mean = conf_min = conf_max = 0.0
        low_conf = high_conf = 0

    sample_boxes = list(boxes[:300])
    overlap_pairs = 0
    for i in range(len(sample_boxes)):
        for j in range(i + 1, len(sample_boxes)):
            if _iou(sample_boxes[i].bbox, sample_boxes[j].bbox) > 0.5:
                overlap_pairs += 1

    class_counts = Counter(box.class_name for box in boxes)
    class_statistics = dict(
        sorted(class_counts.items(), key=lambda item: (-item[1], item[0]))
    )

    return {
        "image": {
            "width": safe_w,
            "height": safe_h,
            "megapixels": round(megapixels, 3),
        },
        "total_objects": total,
        "class_statistics": class_statistics,
        "density": {
            "per_megapixel": round(density, 2),
            "level": _density_level(density),
            "thresholds": "稀疏<5，中等5-20，密集20-50，极密集>50（目标/百万像素）",
        },
        "grid_3x3": {
            "cells": grid_counts,
            "percentages": grid_percentages,
            "dominant": dominant,
        },
        "nearest_neighbor": {
            "mean_px": round(nearest_mean, 2),
            "median_px": round(nearest_median, 2),
            "mean_percent_of_diagonal": round(nearest_percent, 2),
            "sampled": nearest_sampled,
        },
        "edge": {
            "count": edge_count,
            "ratio": round((edge_count / total) if total else 0.0, 4),
        },
        "size_distribution": {
            "counts": size_counts,
            "percentages": size_percentages,
            "definition": "面积占图像比例：小<0.1%，中0.1%-1%，大>1%",
        },
        "confidence": {
            "mean": round(conf_mean, 4),
            "min": round(conf_min, 4),
            "max": round(conf_max, 4),
            "low_confidence_threshold": 0.4,
            "low_confidence_count": low_conf,
            "high_confidence_threshold": 0.7,
            "high_confidence_count": high_conf,
        },
        "overlap": {
            "pairs_iou_gt_0_5": overlap_pairs,
            "sampled": len(sample_boxes),
        },
    }


def sample_boxes(boxes: Sequence[BoxRecord], limit: int = 30) -> List[Dict[str, object]]:
    """Return a small, deterministic sample of boxes for the prompt."""
    ordered = sorted(boxes, key=lambda item: item.confidence, reverse=True)[:limit]
    return [
        {
            "class_name": box.class_name,
            "confidence": round(box.confidence, 4),
            "bbox": list(box.bbox),
        }
        for box in ordered
    ]
