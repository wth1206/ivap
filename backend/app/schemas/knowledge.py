"""Knowledge base API schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer

from app.utils.time import to_iso


class KnowledgeDocumentResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str
    file_size: int
    page_count: Optional[int] = None
    chunk_count: int
    embedding_model: str
    status: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return to_iso(value)


class KnowledgeDocumentListResponse(BaseModel):
    items: List[KnowledgeDocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class KnowledgeDeleteResponse(BaseModel):
    deleted: bool
    document_id: str
    removed_vectors: int


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    document_ids: Optional[List[str]] = None


class KnowledgeSearchItem(BaseModel):
    document_id: str
    document_name: str
    page_no: Optional[int] = None
    chunk_index: int
    content: str
    score: float
    extra: Optional[Dict[str, Any]] = None


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: List[KnowledgeSearchItem]
    no_answer: bool


class Citation(BaseModel):
    index: int
    document_id: str
    document_name: str
    page_no: Optional[int] = None
    chunk_index: int
    score: float
    snippet: str


class KnowledgeAskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    document_ids: Optional[List[str]] = None


class KnowledgeAskResponse(BaseModel):
    query: str
    answer: str
    citations: List[Citation]
    no_answer: bool
    is_mock: bool = False
