"""Analysis report endpoints."""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.analysis import AnalysisReportResponse, AnalysisRequest
from app.services import analysis_service

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post(
    "/{task_id}",
    response_model=AnalysisReportResponse,
    summary="为检测任务生成分析报告",
    description="Python 计算统计事实，LLM 只负责组织语言；force=true 可重新生成。",
)
async def create_analysis(
    task_id: str = Path(..., min_length=32, max_length=32),
    payload: Optional[AnalysisRequest] = Body(default=None),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnalysisReportResponse:
    force = bool(payload.force) if payload else False
    return await analysis_service.generate_report(
        session=session,
        task_id=task_id,
        settings=settings,
        force=force,
    )


@router.get(
    "/{task_id}",
    response_model=AnalysisReportResponse,
    summary="查询任务的最新分析报告",
)
def get_analysis(
    task_id: str = Path(..., min_length=32, max_length=32),
    session: Session = Depends(get_db),
) -> AnalysisReportResponse:
    return analysis_service.get_report(session, task_id)
