"""Knowledge base ingestion, retrieval and RAG question answering."""

import asyncio
import logging
import math
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.rag.chain import answer_question
from app.rag.embeddings import EmbeddingService
from app.rag.loaders import parse_document
from app.rag.splitter import split_document
from app.rag.vector_store import get_vector_store
from app.schemas.knowledge import (
    Citation,
    KnowledgeAskResponse,
    KnowledgeDeleteResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    KnowledgeSearchItem,
    KnowledgeSearchResponse,
)
from app.services.storage import StorageService
from app.utils.ids import new_id
from app.utils.image import sha256_bytes

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {".pdf": "pdf", ".docx": "docx", ".txt": "txt"}


def _validate_document(data: bytes, filename: str, max_mb: int) -> Tuple[str, str]:
    extension = Path(filename or "").suffix.lower()
    file_type = ALLOWED_TYPES.get(extension)
    if file_type is None:
        raise AppError(
            "INVALID_FILE_TYPE",
            "知识库仅支持 PDF、DOCX、TXT",
            400,
            {"extension": extension},
        )
    if not data:
        raise AppError("INVALID_DOCUMENT", "上传的文档为空", 400)
    if len(data) > max_mb * 1024 * 1024:
        raise AppError(
            "FILE_TOO_LARGE",
            f"文档超过 {max_mb} MB 限制",
            413,
            {"max_mb": max_mb, "actual_bytes": len(data)},
        )
    if file_type == "pdf" and not data.startswith(b"%PDF"):
        raise AppError("INVALID_DOCUMENT", "文件内容不是有效的 PDF", 400)
    if file_type == "docx" and not data.startswith(b"PK\x03\x04"):
        raise AppError("INVALID_DOCUMENT", "文件内容不是有效的 DOCX", 400)
    return extension, file_type


def _document_response(document: KnowledgeDocument) -> KnowledgeDocumentResponse:
    return KnowledgeDocumentResponse(
        document_id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        embedding_model=document.embedding_model,
        status=document.status,
        created_at=document.created_at,
    )


def get_document(session: Session, document_id: str) -> KnowledgeDocument:
    document = session.get(KnowledgeDocument, document_id)
    if document is None:
        raise AppError(
            "DOCUMENT_NOT_FOUND",
            "知识库文档不存在",
            404,
            {"document_id": document_id},
        )
    return document


async def upload_document(
    session: Session,
    storage: StorageService,
    settings: Settings,
    data: bytes,
    filename: str,
) -> KnowledgeDocumentResponse:
    extension, file_type = _validate_document(data, filename, settings.max_document_mb)
    sha256 = sha256_bytes(data)

    existing = session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.sha256 == sha256)
    ).scalar_one_or_none()
    if existing is not None:
        raise AppError(
            "DOCUMENT_DUPLICATED",
            "该文档已存在",
            409,
            {"document_id": existing.id, "filename": existing.filename},
        )

    document_id = new_id()
    stored_path = storage.save_document(document_id, data, extension)
    safe_name = Path(filename or f"document{extension}").name[:255]
    document = KnowledgeDocument(
        id=document_id,
        filename=safe_name,
        stored_path=stored_path,
        file_type=file_type,
        file_size=len(data),
        sha256=sha256,
        page_count=None,
        chunk_count=0,
        embedding_model=settings.embedding_model,
        embedding_dim=settings.embedding_dim,
        status="processing",
    )
    try:
        session.add(document)
        session.commit()
        session.refresh(document)
    except Exception:
        session.rollback()
        storage.delete(stored_path)
        raise

    added_ids: List[int] = []
    try:
        parsed = await asyncio.to_thread(
            parse_document, storage.resolve(stored_path), file_type
        )
        chunks = await asyncio.to_thread(
            split_document,
            parsed,
            settings.rag_chunk_size,
            settings.rag_chunk_overlap,
        )
        if not chunks:
            raise AppError("DOCUMENT_NO_TEXT", "文档切分后没有有效文本", 400)

        embedder = EmbeddingService(settings)
        try:
            vectors = await embedder.embed_documents([chunk.content for chunk in chunks])
        finally:
            await embedder.aclose()

        if vectors.shape[0] != len(chunks):
            raise AppError("EMBEDDING_UPSTREAM_ERROR", "Embedding 数量与切片数量不一致", 502)

        store = get_vector_store(settings)
        store.ensure(session)

        rows = [
            KnowledgeChunk(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                page_no=chunk.page_no,
                content=chunk.content,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                extra=chunk.extra,
                embedding=vectors[index].tolist(),
            )
            for index, chunk in enumerate(chunks)
        ]
        session.add_all(rows)
        session.flush()
        for row in rows:
            row.faiss_id = row.id
        ids = [int(row.id) for row in rows]
        store.add(ids, vectors)
        added_ids = ids

        document.status = "ready"
        document.page_count = parsed.page_count
        document.chunk_count = len(rows)
        document.error_message = None
        session.commit()
    except Exception as exc:
        session.rollback()
        if added_ids:
            try:
                get_vector_store(settings).remove(added_ids)
            except Exception:  # pragma: no cover - best effort
                logger.exception("Failed to remove vectors after failed ingest")
        failed = session.get(KnowledgeDocument, document_id)
        if failed is not None:
            failed.status = "failed"
            failed.error_message = str(exc)[:2000]
            session.commit()
        if isinstance(exc, AppError):
            raise
        logger.exception("Document ingest failed: %s", document_id)
        raise AppError(
            "DOCUMENT_INGEST_FAILED",
            "文档解析或向量化失败",
            502,
            {"reason": str(exc)[:300]},
        ) from exc

    session.refresh(document)
    logger.info(
        "Document %s ready: type=%s pages=%s chunks=%d",
        document_id,
        file_type,
        document.page_count,
        document.chunk_count,
    )
    return _document_response(document)


def list_documents(
    session: Session,
    page: int,
    page_size: int,
) -> KnowledgeDocumentListResponse:
    total = session.execute(
        select(func.count()).select_from(KnowledgeDocument)
    ).scalar_one()
    documents = (
        session.execute(
            select(KnowledgeDocument)
            .order_by(KnowledgeDocument.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return KnowledgeDocumentListResponse(
        items=[_document_response(item) for item in documents],
        total=int(total),
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


def delete_document(
    session: Session,
    storage: StorageService,
    settings: Settings,
    document_id: str,
) -> KnowledgeDeleteResponse:
    document = get_document(session, document_id)
    chunk_ids = [
        int(value)
        for value in session.execute(
            select(KnowledgeChunk.id).where(KnowledgeChunk.document_id == document_id)
        ).scalars()
    ]
    stored_path = document.stored_path
    try:
        session.delete(document)
        session.commit()
    except Exception:
        session.rollback()
        raise

    try:
        store = get_vector_store(settings)
        store.ensure(session)
        store.remove(chunk_ids)
    except Exception:  # pragma: no cover - index rebuilds on next use
        logger.exception("Failed to update FAISS after deleting document %s", document_id)

    storage.delete(stored_path)
    logger.info("Deleted knowledge document %s (%d vectors)", document_id, len(chunk_ids))
    return KnowledgeDeleteResponse(
        deleted=True,
        document_id=document_id,
        removed_vectors=len(chunk_ids),
    )


async def search_documents(
    session: Session,
    settings: Settings,
    query: str,
    top_k: int,
    score_threshold: float,
    document_ids: Optional[Sequence[str]] = None,
) -> KnowledgeSearchResponse:
    embedder = EmbeddingService(settings)
    try:
        query_vector = await embedder.embed_query(query)
    finally:
        await embedder.aclose()

    store = get_vector_store(settings)
    store.ensure(session)
    raw = store.search(query_vector, top_k * 3)
    if not raw:
        return KnowledgeSearchResponse(query=query, results=[], no_answer=True)

    ids = [chunk_id for chunk_id, _score in raw]
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(
            KnowledgeChunk.id.in_(ids),
            KnowledgeDocument.status == "ready",
        )
    )
    if document_ids:
        stmt = stmt.where(KnowledgeDocument.id.in_(list(document_ids)))
    rows = session.execute(stmt).all()
    by_id = {int(chunk.id): (chunk, document) for chunk, document in rows}

    results: List[KnowledgeSearchItem] = []
    for chunk_id, score in raw:
        if float(score) < score_threshold:
            continue
        pair = by_id.get(chunk_id)
        if pair is None:
            continue
        chunk, document = pair
        results.append(
            KnowledgeSearchItem(
                document_id=document.id,
                document_name=document.filename,
                page_no=chunk.page_no,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=round(float(score), 4),
                extra=chunk.extra,
            )
        )
        if len(results) >= top_k:
            break

    return KnowledgeSearchResponse(
        query=query,
        results=results,
        no_answer=not results,
    )


def _citations(results: List[KnowledgeSearchItem]) -> List[Citation]:
    return [
        Citation(
            index=index,
            document_id=item.document_id,
            document_name=item.document_name,
            page_no=item.page_no,
            chunk_index=item.chunk_index,
            score=item.score,
            snippet=item.content[:300],
        )
        for index, item in enumerate(results, start=1)
    ]


async def ask_knowledge(
    session: Session,
    settings: Settings,
    query: str,
    top_k: int,
    score_threshold: float,
    document_ids: Optional[Sequence[str]] = None,
) -> KnowledgeAskResponse:
    search = await search_documents(
        session=session,
        settings=settings,
        query=query,
        top_k=top_k,
        score_threshold=score_threshold,
        document_ids=document_ids,
    )
    if search.no_answer:
        return KnowledgeAskResponse(
            query=query,
            answer="知识库中未检索到与该问题相关的内容，无法基于知识库回答。",
            citations=[],
            no_answer=True,
            is_mock=False,
        )

    rag_answer = await answer_question(settings, query, search.results)
    return KnowledgeAskResponse(
        query=query,
        answer=rag_answer.answer,
        citations=_citations(search.results),
        no_answer=False,
        is_mock=rag_answer.is_mock,
    )


def health(session: Session, settings: Settings) -> dict:
    try:
        documents = session.execute(
            select(func.count()).select_from(KnowledgeDocument)
        ).scalar_one()
        vectors = session.execute(
            select(func.count()).select_from(KnowledgeChunk)
        ).scalar_one()
        return {
            "status": "ok",
            "documents": int(documents),
            "vectors": int(vectors),
            "embedding_model": settings.embedding_model,
            "detail": None,
        }
    except Exception as exc:  # pragma: no cover - DB failure path
        logger.warning("Knowledge health check failed: %s", exc)
        return {
            "status": "error",
            "documents": 0,
            "vectors": 0,
            "embedding_model": settings.embedding_model,
            "detail": str(exc)[:300],
        }
