"""Chat API schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer

from app.schemas.knowledge import Citation
from app.utils.time import to_iso


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(default=None, min_length=32, max_length=32)
    task_id: Optional[str] = Field(default=None, min_length=32, max_length=32)
    image_path: Optional[str] = Field(default=None, max_length=512)


class ToolCallLog(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    status: str
    duration_ms: int = 0
    error_code: Optional[str] = None


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: int
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    tool_calls: List[ToolCallLog] = Field(default_factory=list)
    requires_confirmation: bool = False
    usage: ChatUsage = Field(default_factory=ChatUsage)
    is_mock: bool = False
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return to_iso(value)


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    last_message: Optional[str] = None
    updated_at: datetime

    @field_serializer("updated_at")
    def _serialize_updated_at(self, value: datetime) -> str:
        return to_iso(value)


class ConversationInfo(BaseModel):
    conversation_id: str
    title: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _serialize_dates(self, value: datetime) -> str:
        return to_iso(value)


class ChatMessageItem(BaseModel):
    message_id: int
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    citations: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return to_iso(value)


class ChatConversationListResponse(BaseModel):
    items: List[ConversationSummary]
    total: int
    page: int
    page_size: int


class ChatHistoryResponse(BaseModel):
    conversation: ConversationInfo
    items: List[ChatMessageItem]
    total: int
    page: int
    page_size: int
