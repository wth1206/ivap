"""Detection request/response schemas."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.utils.time import to_iso


class DetectionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    class_id: int
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: List[int] = Field(min_length=4, max_length=4, description="[x1, y1, x2, y2]")


class DetectionTaskSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    image_name: str
    model_name: str
    status: str
    total_objects: int
    inference_time_ms: Optional[int] = None
    image_url: Optional[str] = None
    result_image: Optional[str] = None
    is_mock: bool = False
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return to_iso(value)


class DetectionTaskDetail(DetectionTaskSummary):
    image_url: str
    width: int
    height: int
    class_statistics: Optional[Dict[str, int]] = None
    detections: List[DetectionItem] = Field(default_factory=list)
    report_available: bool = False


class DetectionTaskListResponse(BaseModel):
    items: List[DetectionTaskSummary]
    total: int
    page: int
    page_size: int
    pages: int


class DetectionTaskDeleteResponse(BaseModel):
    deleted: bool
    task_id: str


class ModelInfo(BaseModel):
    key: str
    display_name: str
    adapter: str
    available: bool
    loaded: bool
    device: str
    imgsz: int
    conf: float
    iou: float
    is_mock: bool
    default: bool


class ModelListResponse(BaseModel):
    default_model: Optional[str] = None
    models: List[ModelInfo]


class DetectionOverviewResponse(BaseModel):
    total_tasks: int
    total_objects: int
    class_statistics: Dict[str, int]
