"""P4 analysis API tests using LLM_MOCK=true (no network)."""

import io

from PIL import Image


def _image_bytes(width: int = 320, height: int = 240) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (40, 80, 120)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _create_mock_detection(client) -> str:
    response = client.post(
        "/api/v1/detection/predict",
        files={"file": ("analysis.jpg", _image_bytes(), "image/jpeg")},
        data={"model_name": "mock"},
    )
    assert response.status_code == 200, response.text
    return response.json()["task_id"]


def test_create_and_get_mock_analysis(client):
    task_id = _create_mock_detection(client)

    response = client.post(f"/api/v1/analysis/{task_id}")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["task_id"] == task_id
    assert payload["is_mock"] is True
    assert payload["model_name"] == "llm-mock"
    assert payload["prompt_version"] == "analysis-v1"
    assert payload["report_id"] > 0
    assert payload["usage"] == {"prompt_tokens": 0, "completion_tokens": 0}
    assert payload["created_at"].endswith("Z")

    sections = payload["structured"]
    expected = {
        "basic_info",
        "overall_count",
        "class_distribution",
        "density_analysis",
        "spatial_distribution",
        "characteristics",
        "limitations",
        "conclusion",
    }
    assert set(sections) == expected
    assert all(isinstance(value, str) and value for value in sections.values())
    assert "## 1. 检测任务基本信息" in payload["content"]
    assert "## 8. 总结" in payload["content"]

    fetched = client.get(f"/api/v1/analysis/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json()["report_id"] == payload["report_id"]


def test_force_regenerates_report(client):
    task_id = _create_mock_detection(client)
    first = client.post(f"/api/v1/analysis/{task_id}").json()
    second = client.post(f"/api/v1/analysis/{task_id}", json={"force": True}).json()

    assert second["report_id"] > first["report_id"]
    assert client.get(f"/api/v1/analysis/{task_id}").json()["report_id"] == second["report_id"]


def test_pending_task_cannot_be_analysed(client):
    uploaded = client.post(
        "/api/v1/detection/upload",
        files={"file": ("pending.jpg", _image_bytes(), "image/jpeg")},
    )
    task_id = uploaded.json()["task_id"]

    response = client.post(f"/api/v1/analysis/{task_id}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TASK_NOT_READY"


def test_analysis_missing_task(client):
    response = client.get("/api/v1/analysis/" + "0" * 32)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_report_missing(client):
    task_id = _create_mock_detection(client)
    response = client.get(f"/api/v1/analysis/{task_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"
