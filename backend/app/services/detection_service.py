"""Detection task persistence, inference orchestration and queries."""

import logging
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
from PIL import Image
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.algorithms.model_manager import ModelManager
from app.algorithms.visualize import draw_detections
from app.core.config import Settings
from app.core.exceptions import AppError
from app.models.detection import DetectionResult, DetectionTask
from app.models.report import LLMReport
from app.schemas.detection import (
    DetectionItem,
    DetectionTaskDetail,
    DetectionTaskListResponse,
    DetectionTaskSummary,
)
from app.services.storage import StorageService
from app.utils.image import validate_image_bytes

logger = logging.getLogger(__name__)


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def create_task_from_upload(
    session: Session,
    storage: StorageService,
    image: Image.Image,
    raw_bytes: bytes,
    original_name: str,
    model_name: str,
    conf: float,
    iou: float,
    model_version: Optional[str] = None,
    is_mock: bool = False,
) -> DetectionTask:
    """Persist the image and create a pending detection task.

    The file is written first; if the DB transaction fails, it is removed.
    """
    safe_name = Path(original_name or "upload.jpg").name[:255] or "upload.jpg"
    stored = storage.save_image(image, raw_bytes, safe_name)
    task = DetectionTask(
        image_name=safe_name,
        image_path=stored.relative_path,
        image_sha256=stored.sha256,
        image_width=stored.width,
        image_height=stored.height,
        model_name=model_name,
        model_version=model_version,
        status="pending",
        total_objects=0,
        class_statistics={},
        conf_threshold=conf,
        iou_threshold=iou,
        is_mock=is_mock,
    )
    try:
        session.add(task)
        session.commit()
        session.refresh(task)
    except Exception:
        session.rollback()
        storage.delete(stored.relative_path)
        raise
    return task


def run_prediction(
    session: Session,
    storage: StorageService,
    task: DetectionTask,
    manager: ModelManager,
    image_bgr: np.ndarray,
    image_pil: Image.Image,
    conf: float,
    iou: float,
) -> DetectionTask:
    """Run the detector, persist results and annotate the result image.

    The task is marked ``running`` before inference and ``failed`` with a
    readable message on any error, so the UI never sees a stuck task.
    """
    task.status = "running"
    session.commit()

    result_relative: Optional[str] = None
    try:
        detections, elapsed_ms = manager.predict_sync(task.model_name, image_bgr, conf, iou)

        annotated = draw_detections(image_pil, detections)
        result_relative = storage.save_result_image(task.id, annotated)

        statistics = Counter(detection.class_name for detection in detections)
        ordered_statistics = dict(
            sorted(statistics.items(), key=lambda item: (-item[1], item[0]))
        )

        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            session.add(
                DetectionResult(
                    task_id=task.id,
                    class_id=detection.class_id,
                    class_name=detection.class_name,
                    confidence=detection.confidence,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    area=(x2 - x1) * (y2 - y1),
                )
            )

        task.status = "success"
        task.inference_time_ms = elapsed_ms
        task.total_objects = len(detections)
        task.class_statistics = ordered_statistics
        task.result_image_path = result_relative
        task.error_message = None
        session.commit()
    except Exception as exc:
        session.rollback()
        if result_relative:
            storage.delete(result_relative)

        failed = session.get(DetectionTask, task.id)
        if failed is not None:
            failed.status = "failed"
            failed.error_message = str(exc)[:2000]
            session.commit()

        if isinstance(exc, AppError):
            raise
        logger.exception("Detection failed for task %s", task.id)
        raise AppError(
            "DETECTION_FAILED",
            "检测执行失败",
            502,
            {"reason": str(exc)[:300]},
        ) from exc

    session.refresh(task)
    logger.info(
        "Detection task %s success: objects=%d time=%dms model=%s",
        task.id,
        task.total_objects,
        task.inference_time_ms or 0,
        task.model_name,
    )
    return task


def predict_from_bytes(
    session: Session,
    storage: StorageService,
    manager: ModelManager,
    settings: Settings,
    data: bytes,
    filename: str,
    model_name: Optional[str] = None,
    conf: Optional[float] = None,
    iou: Optional[float] = None,
) -> DetectionTask:
    """Validate bytes, run inference and persist a task (used by Agent tool)."""
    image, _extension = validate_image_bytes(data, filename, settings.max_image_mb)
    spec = manager.get_spec(model_name)
    manager.get(spec.key)
    conf_value = float(conf if conf is not None else spec.conf)
    iou_value = float(iou if iou is not None else spec.iou)

    task = create_task_from_upload(
        session=session,
        storage=storage,
        image=image,
        raw_bytes=data,
        original_name=filename,
        model_name=spec.display_name,
        model_version=spec.key,
        is_mock=spec.is_mock,
        conf=conf_value,
        iou=iou_value,
    )
    image_bgr = np.asarray(image)[:, :, ::-1].copy()
    return run_prediction(
        session=session,
        storage=storage,
        task=task,
        manager=manager,
        image_bgr=image_bgr,
        image_pil=image,
        conf=conf_value,
        iou=iou_value,
    )


def list_tasks(
    session: Session,
    page: int,
    page_size: int,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    model_name: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> DetectionTaskListResponse:
    conditions = []
    if keyword:
        conditions.append(DetectionTask.image_name.contains(keyword))
    if status:
        conditions.append(DetectionTask.status == status)
    if model_name:
        conditions.append(DetectionTask.model_name == model_name)
    if start_time:
        conditions.append(DetectionTask.created_at >= _naive_utc(start_time))
    if end_time:
        conditions.append(DetectionTask.created_at <= _naive_utc(end_time))

    total = session.execute(
        select(func.count()).select_from(DetectionTask).where(*conditions)
    ).scalar_one()

    stmt = (
        select(DetectionTask)
        .where(*conditions)
        .order_by(DetectionTask.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    tasks: Sequence[DetectionTask] = session.execute(stmt).scalars().all()
    pages = math.ceil(total / page_size) if total else 0

    return DetectionTaskListResponse(
        items=[DetectionTaskSummary.model_validate(task) for task in tasks],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def get_task(session: Session, task_id: str) -> DetectionTask:
    task = session.get(DetectionTask, task_id)
    if task is None:
        raise AppError("TASK_NOT_FOUND", "检测任务不存在", 404, {"task_id": task_id})
    return task


def get_task_detail(session: Session, task_id: str) -> DetectionTaskDetail:
    task = session.get(DetectionTask, task_id)
    if task is None:
        raise AppError("TASK_NOT_FOUND", "检测任务不存在", 404, {"task_id": task_id})

    results = (
        session.execute(
            select(DetectionResult)
            .where(DetectionResult.task_id == task_id)
            .order_by(DetectionResult.confidence.desc())
        )
        .scalars()
        .all()
    )

    has_report = session.execute(
        select(exists().where(LLMReport.task_id == task_id))
    ).scalar()
    detail = DetectionTaskDetail.model_validate(task)
    detail.detections = [DetectionItem.model_validate(item) for item in results]
    detail.report_available = bool(has_report)
    return detail


def delete_task(session: Session, storage: StorageService, task_id: str) -> DetectionTask:
    task = get_task(session, task_id)
    paths = [task.image_path, task.result_image_path]
    try:
        session.delete(task)
        session.commit()
    except Exception:
        session.rollback()
        raise

    for relative in paths:
        if relative:
            storage.delete(relative)
    logger.info("Deleted detection task %s", task_id)
    return task


def count_tasks(session: Session) -> int:
    return session.execute(select(func.count()).select_from(DetectionTask)).scalar_one()


def get_overview(session: Session) -> dict:
    total_tasks = count_tasks(session)
    total_objects = session.execute(
        select(func.coalesce(func.sum(DetectionTask.total_objects), 0))
    ).scalar_one()
    rows = session.execute(
        select(DetectionResult.class_name, func.count(DetectionResult.id))
        .group_by(DetectionResult.class_name)
        .order_by(func.count(DetectionResult.id).desc(), DetectionResult.class_name)
    ).all()
    return {
        "total_tasks": int(total_tasks),
        "total_objects": int(total_objects or 0),
        "class_statistics": {name: int(count) for name, count in rows},
    }
