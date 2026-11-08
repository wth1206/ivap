"""FastAPI application entry point.

Run from the project root:

    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir backend --reload
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.algorithms.model_manager import get_model_manager
from app.api.v1.endpoints.health import build_health
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

DESCRIPTION = """
基于 YOLO + LLM + RAG 的无人机遥感图像智能视觉分析平台。

* 图像目标检测（ECE-YOLO，可配置权重）
* 检测结果统计与 LLM 分析报告
* RAG 知识库问答（带来源引用）
* LangGraph Agent 工具编排
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings)
    settings.ensure_dirs()

    manager = get_model_manager()
    manager.configure(settings)
    manager.preload()

    logger.info(
        "Starting %s v%s (env=%s)",
        settings.app_name,
        settings.app_version,
        settings.app_env,
    )
    try:
        yield
    finally:
        manager.shutdown()
        logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Application factory (used by uvicorn and by tests)."""
    settings = get_settings()
    settings.ensure_dirs()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "system", "description": "健康检查与系统信息"},
            {"name": "detection", "description": "图像目标检测与任务管理"},
            {"name": "analysis", "description": "LLM 检测分析报告"},
            {"name": "knowledge", "description": "RAG 知识库"},
            {"name": "chat", "description": "Agent 智能对话"},
        ],
    )

    # Last added middleware runs first: request context wraps CORS responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # /static/images/... -> backend/uploads/images/...
    app.mount("/static", StaticFiles(directory=str(settings.upload_dir)), name="static")

    @app.get("/", tags=["system"], summary="项目入口")
    async def root() -> Dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
        }

    @app.get("/health", include_in_schema=False)
    async def health_alias(settings: Settings = Depends(get_settings)) -> HealthResponse:
        """Alias for container health probes; canonical path is /api/v1/health."""
        return build_health(settings)

    return app


app = create_app()
