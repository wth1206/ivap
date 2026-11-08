"""Detection endpoints: upload, predict, task management and model metadata."""

from datetime import datetime
from typing import Literal, Optional

import numpy as np
from fastapi import APIRouter, Depends, File, Form, Path, Query, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.algorithms.model_manager import get_model_manager
from app.api.deps import get_storage
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.detection import (
    DetectionOverviewResponse,
    DetectionTaskDeleteResponse,
    DetectionTaskDetail,
    DetectionTaskListResponse,
    ModelListResponse,
)
from app.services import detection_service
from app.services.storage import StorageService
from app.utils.image import validate_image_bytes

router = APIRouter(prefix="/detection", tags=["detection"])

TaskStatus = Literal["pending", "running", "success", "failed"]


@router.post(
    "/upload",
    response_model=DetectionTaskDetail,
    status_code=status.HTTP_201_CREATED,
    summary="上传图片并创建待检测任务（P2）",
    description="校验并保存 JPG/JPEG/PNG，创建 pending 任务；不执行模型推理。",
)
async def upload_image(
    file: UploadFile = File(..., description="JPG/JPEG/PNG，默认上限 20 MB"),
    model_name: Optional[str] = Form(default=None, max_length=64),
    conf: Optional[float] = Form(default=None, ge=0.0, le=1.0),
    iou: Optional[float] = Form(default=None, ge=0.0, le=1.0),
    session: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> DetectionTaskDetail:
    max_bytes = settings.max_image_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    filename = file.filename or "upload.jpg"
    await file.close()

    image, _extension = validate_image_bytes(data, filename, settings.max_image_mb)
    manager = get_model_manager()
    spec = manager.get_spec(model_name)
    task = detection_service.create_task_from_upload(
        session=session,
        storage=storage,
        image=image,
        raw_bytes=data,
        original_name=filename,
        model_name=spec.display_name,
        model_version=spec.key,
        is_mock=spec.is_mock,
        conf=conf if conf is not None else spec.conf,
        iou=iou if iou is not None else spec.iou,
    )
    return detection_service.get_task_detail(session, task.id)


@router.post(
    "/predict",
    response_model=DetectionTaskDetail,
    summary="上传图片并执行 ECE-YOLO 检测",
    description="执行真实模型推理，保存目标明细、类别统计与结果图。",
)
async def predict_image(
    file: UploadFile = File(..., description="JPG/JPEG/PNG，默认上限 20 MB"),
    model_name: Optional[str] = Form(default=None, max_length=64),
    conf: Optional[float] = Form(default=None, ge=0.0, le=1.0),
    iou: Optional[float] = Form(default=None, ge=0.0, le=1.0),
    session: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> DetectionTaskDetail:
    max_bytes = settings.max_image_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    filename = file.filename or "upload.jpg"
    await file.close()

    image, _extension = validate_image_bytes(data, filename, settings.max_image_mb)
    manager = get_model_manager()
    spec = manager.get_spec(model_name)

    # Load before creating a task: a missing/broken weight should not leave a
    # failed task behind on the very first request.
    await run_in_threadpool(manager.get, spec.key)

    conf_value = conf if conf is not None else spec.conf
    iou_value = iou if iou is not None else spec.iou
    task = detection_service.create_task_from_upload(
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
    await run_in_threadpool(
        detection_service.run_prediction,
        session,
        storage,
        task,
        manager,
        image_bgr,
        image,
        conf_value,
        iou_value,
    )
    return detection_service.get_task_detail(session, task.id)


@router.get(
    "/models",
    response_model=ModelListResponse,
    summary="列出模型配置与就绪状态",
)
def list_models() -> ModelListResponse:
    manager = get_model_manager()
    return ModelListResponse(
        default_model=manager.default_key,
        models=manager.list_models(),
    )


@router.get(
    "/overview",
    response_model=DetectionOverviewResponse,
    summary="首页统计（任务数/目标数/类别分布）",
)
def detection_overview(session: Session = Depends(get_db)) -> DetectionOverviewResponse:
    return DetectionOverviewResponse(**detection_service.get_overview(session))


@router.get(
    "/tasks",
    response_model=DetectionTaskListResponse,
    summary="分页查询检测任务",
)
def list_detection_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: Optional[str] = Query(default=None, max_length=100),
    task_status: Optional[TaskStatus] = Query(default=None, alias="status"),
    model_name: Optional[str] = Query(default=None, max_length=64),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    session: Session = Depends(get_db),
) -> DetectionTaskListResponse:
    return detection_service.list_tasks(
        session=session,
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=task_status,
        model_name=model_name,
        start_time=start_time,
        end_time=end_time,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=DetectionTaskDetail,
    summary="查询任务详情",
)
def get_detection_task(
    task_id: str = Path(..., min_length=32, max_length=32),
    session: Session = Depends(get_db),
) -> DetectionTaskDetail:
    return detection_service.get_task_detail(session, task_id)


@router.delete(
    "/tasks/{task_id}",
    response_model=DetectionTaskDeleteResponse,
    summary="删除任务及其文件",
)
def delete_detection_task(
    task_id: str = Path(..., min_length=32, max_length=32),
    session: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> DetectionTaskDeleteResponse:
    detection_service.delete_task(session, storage, task_id)
    return DetectionTaskDeleteResponse(deleted=True, task_id=task_id)
