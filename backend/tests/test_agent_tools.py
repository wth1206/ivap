"""Direct tests for the five agent tools (mock model/LLM/embedding)."""

import asyncio
import io

from app.agents.tools import (
    ToolContext,
    citations_from_result,
    execute_tool,
)
from app.algorithms.model_manager import get_model_manager
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.storage import StorageService
from PIL import Image


def _image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (320, 240), (10, 30, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _create_mock_task(client) -> dict:
    response = client.post(
        "/api/v1/detection/predict",
        files={"file": ("tool.jpg", _image_bytes(), "image/jpeg")},
        data={"model_name": "mock"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _context(task_id=None, image_path=None):
    settings = get_settings()
    session = get_session_factory()()
    return (
        ToolContext(
            session=session,
            storage=StorageService(settings.upload_dir),
            settings=settings,
            manager=get_model_manager(),
            conversation_id="test-conversation",
            task_id=task_id,
            image_path=image_path,
        ),
        session,
    )


def _run(name, args, context):
    return asyncio.run(execute_tool(name, args, context))


def test_get_detection_result_and_statistics_tools(client):
    task = _create_mock_task(client)
    context, session = _context(task_id=task["task_id"])
    try:
        result, error = _run(
            "get_detection_result",
            {"task_id": task["task_id"], "limit": 10},
            context,
        )
        assert error is None
        assert result["total_objects"] == 3
        assert len(result["detections"]) == 3

        stats, error = _run(
            "get_detection_statistics",
            {"task_id": task["task_id"]},
            context,
        )
        assert error is None
        assert stats["scope"] == "task"
        assert stats["total_objects"] == 3
        assert stats["class_statistics"] == {"mock_object": 3}
    finally:
        session.close()


def test_search_knowledge_base_tool(client):
    content = "VisDrone 数据集包含 car、pedestrian、people 等类别。\n"
    uploaded = client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("tool-kb.txt", content.encode("utf-8"), "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text

    context, session = _context()
    try:
        result, error = _run(
            "search_knowledge_base",
            {"query": "VisDrone 包含哪些类别", "top_k": 3},
            context,
        )
        assert error is None
        assert result["no_answer"] is False
        assert result["results"]
        citations = citations_from_result(result)
        assert citations[0]["document_name"] == "tool-kb.txt"
    finally:
        session.close()


def test_detect_image_tool(client):
    task = _create_mock_task(client)
    detail = client.get(f"/api/v1/detection/tasks/{task['task_id']}").json()
    image_path = detail["image_url"].removeprefix("/static/")

    context, session = _context()
    try:
        result, error = _run(
            "detect_image",
            {"image_path": image_path, "model_name": "mock"},
            context,
        )
        assert error is None
        assert result["status"] == "success"
        assert result["total_objects"] == 3
        assert result["is_mock"] is True
        assert result["result_image"].startswith("/static/results/")
    finally:
        session.close()


def test_generate_analysis_report_tool(client):
    task = _create_mock_task(client)
    context, session = _context(task_id=task["task_id"])
    try:
        result, error = _run(
            "generate_analysis_report",
            {"task_id": task["task_id"]},
            context,
        )
        assert error is None
        assert result["is_mock"] is True
        assert "## 1. 检测任务基本信息" in result["content"]
        assert "## 8. 总结" in result["content"]
    finally:
        session.close()


def test_tool_error_is_returned_not_raised(client):
    context, session = _context()
    try:
        result, error = _run(
            "get_detection_result",
            {"task_id": "0" * 32},
            context,
        )
        assert error == "TASK_NOT_FOUND"
        assert result["error"]["code"] == "TASK_NOT_FOUND"
    finally:
        session.close()
