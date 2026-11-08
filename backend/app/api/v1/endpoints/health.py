"""System health endpoint."""

import logging

from fastapi import APIRouter, Depends

from app.algorithms.model_manager import get_model_manager
from app.core.config import Settings, get_settings
from app.db.session import check_database, get_session_factory
from app.schemas.health import (
    DatabaseHealth,
    DetectorHealth,
    HealthComponents,
    HealthResponse,
    LLMHealth,
    VectorStoreHealth,
)
from app.services import knowledge_service
from app.utils.time import utc_now

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


def build_health(settings: Settings) -> HealthResponse:
    """Build the health payload.

    P1 intentionally reports ``not_configured`` for database/detector/vector
    store: the components are not wired yet, which is different from a fault.
    Later phases replace these values with real probes.
    """
    db_status, db_dialect, db_detail = check_database()
    detector_state = get_model_manager().health()
    knowledge_state = {
        "status": "error",
        "documents": 0,
        "vectors": 0,
        "embedding_model": settings.embedding_model,
        "detail": None,
    }
    try:
        knowledge_session = get_session_factory()()
        try:
            knowledge_state = knowledge_service.health(knowledge_session, settings)
        finally:
            knowledge_session.close()
    except Exception as exc:  # pragma: no cover - defensive
        knowledge_state["detail"] = str(exc)[:300]

    overall_status = (
        "degraded"
        if db_status == "error"
        or detector_state["status"] in {"unavailable", "error"}
        or knowledge_state["status"] == "error"
        else "ok"
    )

    components = HealthComponents(
        database=DatabaseHealth(
            status=db_status,
            dialect=db_dialect,
            detail=db_detail,
        ),
        detector=DetectorHealth(
            status=str(detector_state["status"]),
            model=detector_state.get("model"),
            loaded=bool(detector_state.get("loaded")),
            device=detector_state.get("device"),
            mock=bool(detector_state.get("mock")),
            detail=detector_state.get("detail"),
        ),
        llm=LLMHealth(
            configured=settings.llm_configured,
            model=settings.llm_model or None,
        ),
        vector_store=VectorStoreHealth(
            status=str(knowledge_state["status"]),
            documents=int(knowledge_state.get("documents", 0)),
            vectors=int(knowledge_state.get("vectors", 0)),
            embedding_model=settings.embedding_model,
            detail=knowledge_state.get("detail"),
        ),
    )
    return HealthResponse(
        status=overall_status,
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        time=utc_now(),
        components=components,
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="返回应用、数据库、模型、LLM 与向量库的当前状态。",
)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return build_health(settings)
