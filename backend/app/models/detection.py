"""Detection task and result models."""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import bigint_pk
from app.utils.ids import new_id
from app.utils.time import utc_now_naive


class DetectionTask(Base):
    __tablename__ = "detection_tasks"
    __table_args__ = (
        Index("ix_detection_tasks_created_at", "created_at"),
        Index("ix_detection_tasks_user_created", "user_id", "created_at"),
        Index("ix_detection_tasks_status", "status"),
        Index("ix_detection_tasks_model", "model_name"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    image_name: Mapped[str] = mapped_column(String(255), nullable=False)
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    image_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    image_width: Mapped[int] = mapped_column(Integer, nullable=False)
    image_height: Mapped[int] = mapped_column(Integer, nullable=False)
    result_image_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    inference_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_objects: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    class_statistics: Mapped[Optional[Dict[str, int]]] = mapped_column(JSON, nullable=True)

    conf_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)
    iou_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now_naive
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )

    user = relationship("User", back_populates="detection_tasks")
    results = relationship(
        "DetectionResult",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DetectionResult.confidence.desc()",
    )
    reports = relationship(
        "LLMReport",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def task_id(self) -> str:
        return self.id

    @property
    def width(self) -> int:
        return self.image_width

    @property
    def height(self) -> int:
        return self.image_height

    @property
    def image_url(self) -> str:
        return f"/static/{self.image_path}"

    @property
    def result_image(self) -> Optional[str]:
        return f"/static/{self.result_image_path}" if self.result_image_path else None

    def __repr__(self) -> str:
        return f"<DetectionTask id={self.id} status={self.status!r}>"


class DetectionResult(Base):
    __tablename__ = "detection_results"
    __table_args__ = (
        Index("ix_detection_results_task", "task_id"),
        Index("ix_detection_results_task_class", "task_id", "class_name"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("detection_tasks.id", ondelete="CASCADE"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    x1: Mapped[int] = mapped_column(Integer, nullable=False)
    y1: Mapped[int] = mapped_column(Integer, nullable=False)
    x2: Mapped[int] = mapped_column(Integer, nullable=False)
    y2: Mapped[int] = mapped_column(Integer, nullable=False)
    area: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now_naive
    )

    task = relationship("DetectionTask", back_populates="results")

    @property
    def bbox(self) -> List[int]:
        return [self.x1, self.y1, self.x2, self.y2]

    def __repr__(self) -> str:
        return f"<DetectionResult {self.class_name} {self.confidence:.3f}>"
