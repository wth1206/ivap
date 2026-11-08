"""Agent chat endpoints."""

from typing import Optional, Union

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.algorithms.model_manager import get_model_manager
from app.api.deps import get_storage
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.chat import (
    ChatConversationListResponse,
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
)
from app.services import chat_service
from app.services.storage import StorageService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="与 LangGraph Agent 对话",
    description="自然语言调用检测、任务查询、统计、RAG 与报告工具。",
)
async def chat(
    payload: ChatRequest,
    session: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    return await chat_service.chat(
        session=session,
        storage=storage,
        settings=settings,
        manager=get_model_manager(),
        message=payload.message,
        conversation_id=payload.conversation_id,
        task_id=payload.task_id,
        image_path=payload.image_path,
    )


@router.get(
    "/history",
    response_model=Union[ChatConversationListResponse, ChatHistoryResponse],
    summary="查询会话列表或某个会话的消息",
)
def chat_history(
    conversation_id: Optional[str] = Query(default=None, min_length=32, max_length=32),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
) -> Union[ChatConversationListResponse, ChatHistoryResponse]:
    if conversation_id:
        return chat_service.get_history(session, conversation_id, page, page_size)
    return chat_service.list_conversations(session, page, page_size)
