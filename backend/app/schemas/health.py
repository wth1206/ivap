"""Health-check schemas."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    status: str = Field(description="ok | degraded | not_configured | error")
    detail: Optional[str] = None


class DatabaseHealth(ComponentHealth):
    dialect: Optional[str] = None


class DetectorHealth(ComponentHealth):
    model: Optional[str] = None
    loaded: bool = False
    device: Optional[str] = None
    mock: bool = False


class LLMHealth(BaseModel):
    configured: bool = False
    model: Optional[str] = None


class VectorStoreHealth(ComponentHealth):
    documents: int = 0
    vectors: int = 0
    embedding_model: Optional[str] = None


class HealthComponents(BaseModel):
    database: DatabaseHealth
    detector: DetectorHealth
    llm: LLMHealth
    vector_store: VectorStoreHealth


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    environment: str
    time: datetime
    components: HealthComponents
