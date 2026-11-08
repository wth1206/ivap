"""Chat persistence and agent orchestration."""

import logging
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.runner import AgentRunner
from app.agents.tools import ToolContext
from app.algorithms.model_manager import ModelManager
from app.core.config import Settings
from app.core.exceptions import AppError
from app.models.chat import ChatMessage, Conversation
from app.schemas.chat import (
    ChatConversationListResponse,
    ChatHistoryResponse,
    ChatMessageItem,
    ChatResponse,
    ChatUsage,
    ConversationInfo,
    ConversationSummary,
    ToolCallLog,
)
from app.services.storage import StorageService
from app.utils.time import utc_now_naive

logger = logging.getLogger(__name__)


def _conversation(session: Session, conversation_id: str) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise AppError(
            "CONVERSATION_NOT_FOUND",
            "会话不存在",
            404,
            {"conversation_id": conversation_id},
        )
    return conversation


def _history_messages(
    session: Session,
    conversation_id: str,
    limit: int,
) -> List[Dict[str, str]]:
    rows = (
        session.execute(
            select(ChatMessage)
            .where(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.role.in_(("user", "assistant")),
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [{"role": row.role, "content": row.content} for row in reversed(rows)]


async def chat(
    session: Session,
    storage: StorageService,
    settings: Settings,
    manager: ModelManager,
    message: str,
    conversation_id: Optional[str] = None,
    task_id: Optional[str] = None,
    image_path: Optional[str] = None,
) -> ChatResponse:
    if conversation_id:
        conversation = _conversation(session, conversation_id)
    else:
        title = message.strip().replace("\n", " ")[:60] or "新会话"
        conversation = Conversation(title=title, user_id=None)
        session.add(conversation)
        session.commit()
        session.refresh(conversation)

    user_message = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=message,
    )
    session.add(user_message)
    conversation.updated_at = utc_now_naive()
    session.commit()

    history = _history_messages(
        session,
        conversation.id,
        settings.agent_history_limit,
    )
    context = ToolContext(
        session=session,
        storage=storage,
        settings=settings,
        manager=manager,
        conversation_id=conversation.id,
        user_id=None,
        task_id=task_id,
        image_path=image_path,
    )
    runner = AgentRunner(settings, context)
    result = await runner.run(history, task_id=task_id, image_path=image_path)

    assistant_message = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result.answer,
        tool_calls=result.tool_calls or None,
        citations=result.citations or None,
        token_usage=result.usage or None,
    )
    session.add(assistant_message)
    conversation.updated_at = utc_now_naive()
    session.commit()
    session.refresh(assistant_message)

    logger.info(
        "Chat %s assistant message %s tools=%d citations=%d",
        conversation.id,
        assistant_message.id,
        len(result.tool_calls),
        len(result.citations),
    )
    return ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        answer=assistant_message.content,
        citations=result.citations,
        tool_calls=[ToolCallLog(**item) for item in result.tool_calls],
        requires_confirmation=result.requires_confirmation,
        usage=ChatUsage(
            prompt_tokens=int(result.usage.get("prompt_tokens", 0)),
            completion_tokens=int(result.usage.get("completion_tokens", 0)),
        ),
        is_mock=settings.llm_mock,
        created_at=assistant_message.created_at,
    )


def list_conversations(
    session: Session,
    page: int,
    page_size: int,
) -> ChatConversationListResponse:
    total = session.execute(
        select(func.count()).select_from(Conversation)
    ).scalar_one()
    conversations = (
        session.execute(
            select(Conversation)
            .order_by(Conversation.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    items = []
    for conversation in conversations:
        last_message = session.execute(
            select(ChatMessage.content)
            .where(ChatMessage.conversation_id == conversation.id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        items.append(
            ConversationSummary(
                conversation_id=conversation.id,
                title=conversation.title,
                last_message=(last_message or "")[:200] or None,
                updated_at=conversation.updated_at,
            )
        )
    return ChatConversationListResponse(
        items=items,
        total=int(total),
        page=page,
        page_size=page_size,
    )


def get_history(
    session: Session,
    conversation_id: str,
    page: int,
    page_size: int,
) -> ChatHistoryResponse:
    conversation = _conversation(session, conversation_id)
    total = session.execute(
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
    ).scalar_one()
    messages = (
        session.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    items = [
        ChatMessageItem(
            message_id=item.id,
            role=item.role,
            content=item.content,
            tool_calls=item.tool_calls,
            citations=item.citations,
            created_at=item.created_at,
        )
        for item in messages
    ]
    return ChatHistoryResponse(
        conversation=ConversationInfo(
            conversation_id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        ),
        items=items,
        total=int(total),
        page=page,
        page_size=page_size,
    )
