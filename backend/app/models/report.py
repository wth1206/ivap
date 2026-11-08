"""LLM analysis report model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import bigint_pk
from app.utils.time import utc_now_naive


class LLMReport(Base):
    __tablename__ = "llm_reports"
    __table_args__ = (
        Index("ix_llm_reports_task_created", "task_id", "created_at"),
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
    report_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="detection_analysis"
    )
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(
        Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False
    )
    structured: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now_naive
    )

    task = relationship("DetectionTask", back_populates="reports")

    def __repr__(self) -> str:
        return f"<LLMReport id={self.id} task_id={self.task_id}>"
