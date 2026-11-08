"""Tool registry for the IVAP LangGraph agent."""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.algorithms.model_manager import ModelManager
from app.core.config import Settings
from app.core.exceptions import AppError
from app.models.detection import DetectionResult, DetectionTask
from app.services import analysis_service, detection_service, knowledge_service
from app.services.storage import StorageService
from app.utils.time import to_iso

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    session: Session
    storage: StorageService
    settings: Settings
    manager: ModelManager
    conversation_id: str
    user_id: Optional[int] = None
    task_id: Optional[str] = None
    image_path: Optional[str] = None


class DetectImageArgs(BaseModel):
    image_path: Optional[str] = Field(default=None, max_length=512)
    model_name: Optional[str] = Field(default=None, max_length=64)
    conf: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    iou: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class GetResultArgs(BaseModel):
    task_id: Optional[str] = Field(default=None, min_length=32, max_length=32)
    include_detections: bool = True
    limit: int = Field(default=100, ge=1, le=200)


class GetStatisticsArgs(BaseModel):
    task_id: Optional[str] = Field(default=None, min_length=32, max_length=32)
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class GenerateReportArgs(BaseModel):
    task_id: Optional[str] = Field(default=None, min_length=32, max_length=32)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    args_model: type
    handler: Callable[[ToolContext, Dict[str, Any]], Awaitable[Dict[str, Any]]]


def _task_id(args: Dict[str, Any], context: ToolContext) -> str:
    value = args.get("task_id") or context.task_id
    if not value:
        raise AppError(
            "TASK_ID_REQUIRED",
            "请提供检测任务 ID，或先在检测页面选择任务",
            400,
        )
    return str(value)


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppError(
            "INVALID_DATETIME",
            f"时间格式无效：{value}",
            400,
        ) from exc


def _normalise_image_path(path: str) -> str:
    path = path.strip()
    if path.startswith("/static/"):
        return path[len("/static/") :]
    return path


async def _detect_image(context: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    path_value = args.get("image_path") or context.image_path
    if not path_value:
        raise AppError(
            "IMAGE_PATH_REQUIRED",
            "请先上传图片，或在消息中提供 uploads 下的图片相对路径",
            400,
        )
    relative = _normalise_image_path(str(path_value))
    if relative.startswith(("http://", "https://")):
        raise AppError("INVALID_IMAGE_PATH", "image_path 必须是服务器内部相对路径", 400)

    file_path = context.storage.resolve(relative)
    if not file_path.is_file():
        raise AppError(
            "IMAGE_NOT_FOUND",
            "图片不存在",
            404,
            {"image_path": relative},
        )
    if file_path.stat().st_size > context.settings.max_image_mb * 1024 * 1024:
        raise AppError("FILE_TOO_LARGE", "图片超过大小限制", 413)

    data = file_path.read_bytes()
    task = await asyncio.to_thread(
        detection_service.predict_from_bytes,
        context.session,
        context.storage,
        context.manager,
        context.settings,
        data,
        file_path.name,
        args.get("model_name"),
        args.get("conf"),
        args.get("iou"),
    )
    detail = detection_service.get_task_detail(context.session, task.id)
    return {
        "task_id": detail.task_id,
        "status": detail.status,
        "model_name": detail.model_name,
        "image_name": detail.image_name,
        "width": detail.width,
        "height": detail.height,
        "total_objects": detail.total_objects,
        "class_statistics": detail.class_statistics or {},
        "result_image": detail.result_image,
        "is_mock": detail.is_mock,
        "inference_time_ms": detail.inference_time_ms,
    }


async def _get_detection_result(context: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    task_id = _task_id(args, context)
    detail = detection_service.get_task_detail(context.session, task_id)
    detections = []
    if args.get("include_detections", True):
        limit = int(args.get("limit", 100))
        detections = [item.model_dump() for item in detail.detections[:limit]]
    return {
        "task_id": detail.task_id,
        "image_name": detail.image_name,
        "model_name": detail.model_name,
        "status": detail.status,
        "width": detail.width,
        "height": detail.height,
        "total_objects": detail.total_objects,
        "class_statistics": detail.class_statistics or {},
        "result_image": detail.result_image,
        "detections": detections,
        "returned_detections": len(detections),
        "report_available": detail.report_available,
    }


async def _get_statistics(context: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    task_id = args.get("task_id") or context.task_id
    if task_id:
        detail = detection_service.get_task_detail(context.session, task_id)
        return {
            "scope": "task",
            "task_id": detail.task_id,
            "task_count": 1,
            "total_objects": detail.total_objects,
            "class_statistics": detail.class_statistics or {},
        }

    start = _parse_datetime(args.get("start_time"))
    end = _parse_datetime(args.get("end_time"))
    if start is not None and start.tzinfo is not None:
        start = start.astimezone(timezone.utc).replace(tzinfo=None)
    if end is not None and end.tzinfo is not None:
        end = end.astimezone(timezone.utc).replace(tzinfo=None)
    conditions = []
    if start:
        conditions.append(DetectionTask.created_at >= start)
    if end:
        conditions.append(DetectionTask.created_at <= end)

    task_count = context.session.execute(
        select(func.count()).select_from(DetectionTask).where(*conditions)
    ).scalar_one()
    total_objects = context.session.execute(
        select(func.coalesce(func.sum(DetectionTask.total_objects), 0)).where(*conditions)
    ).scalar_one()
    rows = context.session.execute(
        select(DetectionResult.class_name, func.count(DetectionResult.id))
        .join(DetectionTask, DetectionTask.id == DetectionResult.task_id)
        .where(*conditions)
        .group_by(DetectionResult.class_name)
        .order_by(func.count(DetectionResult.id).desc(), DetectionResult.class_name)
    ).all()
    return {
        "scope": "history",
        "task_count": int(task_count),
        "total_objects": int(total_objects or 0),
        "class_statistics": {name: int(count) for name, count in rows},
        "start_time": to_iso(start) if start else None,
        "end_time": to_iso(end) if end else None,
    }


async def _search_knowledge(context: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    response = await knowledge_service.search_documents(
        session=context.session,
        settings=context.settings,
        query=str(args["query"]),
        top_k=int(args.get("top_k", 5)),
        score_threshold=context.settings.rag_score_threshold,
    )
    results = []
    for index, item in enumerate(response.results, start=1):
        payload = item.model_dump()
        payload["index"] = index
        payload["citation"] = f"S{index}"
        results.append(payload)
    return {
        "query": response.query,
        "no_answer": response.no_answer,
        "results": results,
    }


async def _generate_report(context: ToolContext, args: Dict[str, Any]) -> Dict[str, Any]:
    task_id = _task_id(args, context)
    report = await analysis_service.generate_report(
        session=context.session,
        task_id=task_id,
        settings=context.settings,
        force=False,
    )
    return {
        "report_id": report.report_id,
        "task_id": report.task_id,
        "model_name": report.model_name,
        "is_mock": report.is_mock,
        "content": report.content,
        "structured": report.structured.model_dump(),
        "created_at": to_iso(report.created_at),
    }


TOOL_SPECS: List[ToolSpec] = [
    ToolSpec(
        name="detect_image",
        description="对指定图片执行 ECE-YOLO 目标检测，返回 task_id、目标数量与类别统计。",
        parameters={
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "uploads 下相对路径；省略时使用当前会话图片",
                },
                "model_name": {"type": "string", "description": "模型 key，默认 ece-yolo"},
                "conf": {"type": "number", "minimum": 0, "maximum": 1},
                "iou": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        args_model=DetectImageArgs,
        handler=_detect_image,
    ),
    ToolSpec(
        name="get_detection_result",
        description="查询某个检测任务的状态、类别统计与目标框。",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "32 位任务 ID；省略时使用当前任务"},
                "include_detections": {"type": "boolean", "default": True},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 100},
            },
        },
        args_model=GetResultArgs,
        handler=_get_detection_result,
    ),
    ToolSpec(
        name="get_detection_statistics",
        description="统计指定任务或历史任务的检测数量与类别分布。",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务 ID；省略时统计全部历史"},
                "start_time": {"type": "string", "description": "ISO 时间，可选"},
                "end_time": {"type": "string", "description": "ISO 时间，可选"},
            },
        },
        args_model=GetStatisticsArgs,
        handler=_get_statistics,
    ),
    ToolSpec(
        name="search_knowledge_base",
        description="检索知识库，返回文档名、页码、片段与相似度，用于专业问答。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索问题"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["query"],
        },
        args_model=SearchKnowledgeArgs,
        handler=_search_knowledge,
    ),
    ToolSpec(
        name="generate_analysis_report",
        description="为成功完成的检测任务生成 8 段分析报告（数字来自 Python 统计）。",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务 ID；省略时使用当前任务"},
            },
        },
        args_model=GenerateReportArgs,
        handler=_generate_report,
    ),
]

TOOL_MAP = {spec.name: spec for spec in TOOL_SPECS}


def openai_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }
        for spec in TOOL_SPECS
    ]


async def execute_tool(
    name: str,
    arguments: Any,
    context: ToolContext,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Execute a tool.  Returns ``(result, error_code)``; never raises."""
    spec = TOOL_MAP.get(name)
    if spec is None:
        return {
            "error": {"code": "TOOL_NOT_FOUND", "message": f"未知工具：{name}"}
        }, "TOOL_NOT_FOUND"

    try:
        if isinstance(arguments, str):
            payload = json.loads(arguments or "{}")
        else:
            payload = arguments or {}
        if not isinstance(payload, dict):
            raise ValueError("tool arguments must be a JSON object")
        parsed = spec.args_model.model_validate(payload)
        result = await spec.handler(context, parsed.model_dump(exclude_none=True))
        return result, None
    except ValidationError as exc:
        logger.info("Tool %s argument validation failed: %s", name, exc)
        return {
            "error": {
                "code": "INVALID_TOOL_ARGUMENTS",
                "message": "工具参数不合法",
                "details": exc.errors()[:5],
            }
        }, "INVALID_TOOL_ARGUMENTS"
    except AppError as exc:
        logger.info("Tool %s failed: %s", name, exc.message)
        return {
            "error": {"code": exc.code, "message": exc.message, "details": exc.details}
        }, exc.code
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Tool %s crashed", name)
        return {
            "error": {"code": "TOOL_EXECUTION_FAILED", "message": str(exc)[:300]}
        }, "TOOL_EXECUTION_FAILED"


def citations_from_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract citations from a search_knowledge_base result."""
    citations = []
    for item in result.get("results", []) or []:
        citations.append(
            {
                "index": item.get("index"),
                "document_id": item.get("document_id"),
                "document_name": item.get("document_name"),
                "page_no": item.get("page_no"),
                "chunk_index": item.get("chunk_index"),
                "score": item.get("score"),
                "snippet": (item.get("content") or "")[:300],
            }
        )
    return citations
