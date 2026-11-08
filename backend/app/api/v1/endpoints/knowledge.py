"""Knowledge base endpoints: upload, list, delete, search and RAG ask."""

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_storage
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.knowledge import (
    KnowledgeAskRequest,
    KnowledgeAskResponse,
    KnowledgeDeleteResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services import knowledge_service
from app.services.storage import StorageService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post(
    "/upload",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="上传并索引知识文档",
    description="解析 PDF/DOCX/TXT，切分、Embedding、写入 FAISS 与数据库。",
)
async def upload_knowledge(
    file: UploadFile = File(..., description="PDF / DOCX / TXT，默认上限 50 MB"),
    session: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> KnowledgeDocumentResponse:
    max_bytes = settings.max_document_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    filename = file.filename or "document.txt"
    await file.close()
    return await knowledge_service.upload_document(
        session=session,
        storage=storage,
        settings=settings,
        data=data,
        filename=filename,
    )


@router.get(
    "/documents",
    response_model=KnowledgeDocumentListResponse,
    summary="分页查询知识文档",
)
def list_knowledge_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
) -> KnowledgeDocumentListResponse:
    return knowledge_service.list_documents(session, page, page_size)


@router.delete(
    "/documents/{document_id}",
    response_model=KnowledgeDeleteResponse,
    summary="删除知识文档及其向量",
)
def delete_knowledge_document(
    document_id: str = Path(..., min_length=32, max_length=32),
    session: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> KnowledgeDeleteResponse:
    return knowledge_service.delete_document(
        session=session,
        storage=storage,
        settings=settings,
        document_id=document_id,
    )


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    summary="知识库相似度检索",
)
async def search_knowledge(
    payload: KnowledgeSearchRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> KnowledgeSearchResponse:
    return await knowledge_service.search_documents(
        session=session,
        settings=settings,
        query=payload.query,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        document_ids=payload.document_ids,
    )


@router.post(
    "/ask",
    response_model=KnowledgeAskResponse,
    summary="基于知识库回答并返回引用",
)
async def ask_knowledge(
    payload: KnowledgeAskRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> KnowledgeAskResponse:
    return await knowledge_service.ask_knowledge(
        session=session,
        settings=settings,
        query=payload.query,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        document_ids=payload.document_ids,
    )
