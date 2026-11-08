"""Analysis request/response schemas and the strict LLM output contract."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.utils.time import to_iso


class AnalysisSections(BaseModel):
    """Eight fixed sections.  Extra keys from the model are ignored."""

    model_config = ConfigDict(extra="ignore")

    basic_info: str = Field(min_length=1, max_length=8000)
    overall_count: str = Field(min_length=1, max_length=8000)
    class_distribution: str = Field(min_length=1, max_length=8000)
    density_analysis: str = Field(min_length=1, max_length=8000)
    spatial_distribution: str = Field(min_length=1, max_length=8000)
    characteristics: str = Field(min_length=1, max_length=8000)
    limitations: str = Field(min_length=1, max_length=8000)
    conclusion: str = Field(min_length=1, max_length=8000)


class AnalysisRequest(BaseModel):
    force: bool = False


class AnalysisUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class AnalysisReportResponse(BaseModel):
    report_id: int
    task_id: str
    model_name: str
    prompt_version: str
    content: str
    structured: AnalysisSections
    latency_ms: Optional[int] = None
    usage: AnalysisUsage = Field(default_factory=AnalysisUsage)
    is_mock: bool = False
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return to_iso(value)
