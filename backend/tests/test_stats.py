"""Pure-Python statistics tests."""

from app.services.stats import BoxRecord, compute_facts, sample_boxes


def _box(x1, y1, x2, y2, conf=0.8, name="car"):
    return BoxRecord(class_name=name, confidence=conf, bbox=(x1, y1, x2, y2))


def test_corner_boxes_and_grid():
    boxes = [
        _box(0, 0, 10, 10, 0.9),
        _box(990, 0, 1000, 10, 0.8),
        _box(0, 990, 10, 1000, 0.7),
        _box(990, 990, 1000, 1000, 0.6),
    ]
    facts = compute_facts(1000, 1000, boxes)

    assert facts["total_objects"] == 4
    assert facts["class_statistics"] == {"car": 4}
    assert facts["grid_3x3"]["cells"]["左上"] == 1
    assert facts["grid_3x3"]["cells"]["右上"] == 1
    assert facts["grid_3x3"]["cells"]["左下"] == 1
    assert facts["grid_3x3"]["cells"]["右下"] == 1
    assert facts["grid_3x3"]["percentages"]["左上"] == 25.0
    assert facts["density"]["per_megapixel"] == 4.0
    assert facts["density"]["level"] == "稀疏"
    assert facts["edge"]["count"] == 4
    assert facts["edge"]["ratio"] == 1.0
    assert facts["size_distribution"]["counts"]["small"] == 4
    assert facts["confidence"]["mean"] == 0.75
    assert facts["confidence"]["high_confidence_count"] == 3


def test_nearest_neighbor_and_overlap():
    boxes = [_box(0, 0, 60, 60, 0.9), _box(100, 0, 160, 60, 0.8)]
    facts = compute_facts(1000, 1000, boxes)

    assert facts["nearest_neighbor"]["mean_px"] == 100.0
    assert facts["nearest_neighbor"]["median_px"] == 100.0
    assert facts["nearest_neighbor"]["sampled"] == 2
    assert facts["overlap"]["pairs_iou_gt_0_5"] == 0

    overlapping = compute_facts(1000, 1000, [_box(0, 0, 60, 60), _box(0, 0, 60, 60)])
    assert overlapping["overlap"]["pairs_iou_gt_0_5"] == 1


def test_empty_detections():
    facts = compute_facts(640, 480, [])

    assert facts["total_objects"] == 0
    assert facts["class_statistics"] == {}
    assert facts["density"]["level"] == "稀疏"
    assert facts["confidence"]["mean"] == 0.0
    assert facts["grid_3x3"]["dominant"] == "无目标"
    assert facts["edge"]["ratio"] == 0.0


def test_sample_boxes_sorted_and_limited():
    boxes = [_box(0, 0, 10, 10, 0.1 + i * 0.01) for i in range(40)]
    sample = sample_boxes(boxes, limit=5)
    assert len(sample) == 5
    scores = [item["confidence"] for item in sample]
    assert scores == sorted(scores, reverse=True)
