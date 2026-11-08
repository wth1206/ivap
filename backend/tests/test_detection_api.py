"""P2 detection upload and task-management tests (SQLite, no model)."""

import io
from pathlib import Path

from app.core.config import get_settings
from PIL import Image


def _image_bytes(width: int = 320, height: int = 240, color=(90, 120, 150)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def _upload(client, name: str = "uav.jpg", data: bytes = None):
    return client.post(
        "/api/v1/detection/upload",
        files={"file": (name, data if data is not None else _image_bytes(), "image/jpeg")},
    )


def test_upload_creates_pending_task(client):
    response = _upload(client)

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["image_name"] == "uav.jpg"
    assert payload["model_name"] == "ECE-YOLO"
    assert payload["width"] == 320
    assert payload["height"] == 240
    assert payload["total_objects"] == 0
    assert payload["detections"] == []
    assert payload["class_statistics"] == {}
    assert payload["result_image"] is None
    assert payload["report_available"] is False
    assert payload["created_at"].endswith("Z")

    relative = payload["image_url"].removeprefix("/static/")
    assert (get_settings().upload_dir / Path(relative)).is_file()


def test_list_pagination_and_keyword_filter(client):
    assert _upload(client, "alpha.jpg").status_code == 201
    assert _upload(client, "beta.jpg").status_code == 201

    response = client.get("/api/v1/detection/tasks", params={"page": 1, "page_size": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["pages"] == 2
    assert len(payload["items"]) == 1

    filtered = client.get("/api/v1/detection/tasks", params={"keyword": "alpha"})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["image_name"] == "alpha.jpg"


def test_upload_rejects_wrong_extension(client):
    response = _upload(client, "notes.txt", b"hello")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_upload_rejects_broken_image(client):
    response = _upload(client, "broken.jpg", b"not-an-image")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


def test_get_task_not_found(client):
    response = client.get("/api/v1/detection/tasks/" + "0" * 32)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_delete_task_removes_file_and_row(client):
    uploaded = _upload(client).json()
    task_id = uploaded["task_id"]
    relative = uploaded["image_url"].removeprefix("/static/")
    file_path = get_settings().upload_dir / Path(relative)
    assert file_path.is_file()

    response = client.delete(f"/api/v1/detection/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "task_id": task_id}
    assert not file_path.exists()

    assert client.get(f"/api/v1/detection/tasks/{task_id}").status_code == 404
    assert client.get("/api/v1/detection/tasks").json()["total"] == 0


def test_upload_requires_file(client):
    response = client.post("/api/v1/detection/upload")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def _predict(client, model_name: str = "mock", name: str = "uav.jpg", data: bytes = None):
    return client.post(
        "/api/v1/detection/predict",
        files={"file": (name, data if data is not None else _image_bytes(), "image/jpeg")},
        data={"model_name": model_name},
    )


def test_predict_with_mock_detector(client):
    response = _predict(client)
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "success"
    assert payload["is_mock"] is True
    assert payload["total_objects"] == 3
    assert payload["class_statistics"] == {"mock_object": 3}
    assert len(payload["detections"]) == 3
    assert payload["inference_time_ms"] >= 0
    assert payload["result_image"].startswith("/static/results/")
    assert payload["created_at"].endswith("Z")

    relative = payload["result_image"].removeprefix("/static/")
    assert (get_settings().upload_dir / Path(relative)).is_file()
    for detection in payload["detections"]:
        assert detection["class_name"] == "mock_object"
        assert len(detection["bbox"]) == 4


def test_models_endpoint(client):
    response = client.get("/api/v1/detection/models")
    assert response.status_code == 200

    payload = response.json()
    assert payload["default_model"] == "ece-yolo"
    models = {item["key"]: item for item in payload["models"]}
    assert models["ece-yolo"]["display_name"] == "ECE-YOLO"
    assert models["ece-yolo"]["available"] is True
    assert models["ece-yolo"]["is_mock"] is False
    assert models["mock"]["is_mock"] is True


def test_overview_after_prediction(client):
    assert _predict(client).status_code == 200

    response = client.get("/api/v1/detection/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_tasks"] == 1
    assert payload["total_objects"] == 3
    assert payload["class_statistics"] == {"mock_object": 3}


def test_predict_unknown_model(client):
    response = _predict(client, model_name="does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MODEL_NOT_FOUND"
