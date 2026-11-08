"""FAISS index persistence and rebuild.

Vectors are also stored on ``knowledge_chunks.embedding`` so the index can be
rebuilt without calling the embedding API again.
"""

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import faiss
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, directory: Path, dimension: int, embedding_model: str) -> None:
        self.directory = Path(directory).resolve()
        self.dimension = int(dimension)
        self.embedding_model = embedding_model
        self.index_path = self.directory / "index.faiss"
        self.meta_path = self.directory / "meta.json"
        self._index: Optional[faiss.IndexIDMap2] = None
        self._loaded = False
        self._lock = threading.RLock()
        self.directory.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def _new_index(self) -> faiss.IndexIDMap2:
        return faiss.IndexIDMap2(faiss.IndexFlatIP(self.dimension))

    def _load_from_disk(self) -> bool:
        if not self.index_path.is_file() or not self.meta_path.is_file():
            return False
        try:
            meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            if (
                int(meta.get("dimension", -1)) != self.dimension
                or str(meta.get("embedding_model", "")) != self.embedding_model
            ):
                logger.info("FAISS metadata mismatch; rebuilding")
                return False
            index = faiss.read_index(str(self.index_path))
            if not isinstance(index, faiss.IndexIDMap2) or index.d != self.dimension:
                logger.info("FAISS index type/dimension mismatch; rebuilding")
                return False
            self._index = index
            return True
        except Exception as exc:  # pragma: no cover - corrupt index path
            logger.warning("Failed to load FAISS index: %s", exc)
            return False

    @staticmethod
    def _ready_rows(session: Session) -> List[Tuple[int, Sequence[float]]]:
        stmt = (
            select(KnowledgeChunk.id, KnowledgeChunk.embedding)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(
                KnowledgeDocument.status == "ready",
                KnowledgeChunk.embedding.isnot(None),
            )
        )
        return [(int(row[0]), row[1]) for row in session.execute(stmt).all() if row[1]]

    def _rebuild(self, session: Session) -> None:
        rows = self._ready_rows(session)
        index = self._new_index()
        ids: List[int] = []
        vectors: List[np.ndarray] = []
        for chunk_id, embedding in rows:
            vector = np.asarray(embedding, dtype="float32")
            if vector.shape[0] != self.dimension:
                logger.warning(
                    "Skipping chunk %s: embedding dim %s != %s",
                    chunk_id,
                    vector.shape[0],
                    self.dimension,
                )
                continue
            ids.append(chunk_id)
            vectors.append(vector)
        if ids:
            array = np.ascontiguousarray(np.stack(vectors))
            faiss.normalize_L2(array)
            index.add_with_ids(array, np.asarray(ids, dtype="int64"))
        self._index = index
        self._loaded = True
        self.save()
        logger.info("FAISS index rebuilt: %d vectors", index.ntotal)

    def ensure(self, session: Session) -> None:
        """Load the persisted index or rebuild it from DB vectors."""
        with self._lock:
            if self._index is None and not self._load_from_disk():
                self._rebuild(session)
                return
            expected = len(self._ready_rows(session))
            if self._index is None or self._index.ntotal != expected:
                self._rebuild(session)
            self._loaded = True

    # ------------------------------------------------------------------
    # mutations
    # ------------------------------------------------------------------
    def add(self, chunk_ids: Sequence[int], vectors: np.ndarray) -> None:
        with self._lock:
            if self._index is None:
                self._index = self._new_index()
            array = np.ascontiguousarray(np.asarray(vectors, dtype="float32"))
            faiss.normalize_L2(array)
            self._index.add_with_ids(
                array, np.asarray(list(chunk_ids), dtype="int64")
            )
            self.save()

    def remove(self, chunk_ids: Sequence[int]) -> int:
        with self._lock:
            if self._index is None or not chunk_ids:
                return 0
            removed = self._index.remove_ids(
                np.asarray(list(chunk_ids), dtype="int64")
            )
            self.save()
            return int(removed)

    # ------------------------------------------------------------------
    # search / persistence
    # ------------------------------------------------------------------
    def search(self, query_vector: np.ndarray, top_k: int) -> List[Tuple[int, float]]:
        with self._lock:
            if self._index is None or self._index.ntotal == 0:
                return []
            query = np.ascontiguousarray(
                np.asarray([query_vector], dtype="float32")
            )
            faiss.normalize_L2(query)
            limit = min(max(1, top_k), int(self._index.ntotal))
            scores, ids = self._index.search(query, limit)
            results = []
            for score, chunk_id in zip(scores[0], ids[0]):
                if int(chunk_id) < 0:
                    continue
                results.append((int(chunk_id), float(score)))
            return results

    def save(self) -> None:
        if self._index is None:
            return
        tmp_index = self.index_path.with_suffix(".faiss.tmp")
        faiss.write_index(self._index, str(tmp_index))
        os.replace(tmp_index, self.index_path)

        meta = {
            "dimension": self.dimension,
            "embedding_model": self.embedding_model,
            "count": int(self._index.ntotal),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        tmp_meta = self.meta_path.with_suffix(".json.tmp")
        tmp_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_meta, self.meta_path)

    @property
    def count(self) -> int:
        return int(self._index.ntotal) if self._index is not None else 0

    def reset(self) -> None:
        with self._lock:
            self._index = None
            self._loaded = False


_store: Optional[VectorStore] = None
_store_lock = threading.Lock()


def get_vector_store(settings: Settings) -> VectorStore:
    global _store
    directory = settings.vector_db_dir.resolve()
    with _store_lock:
        if (
            _store is None
            or _store.directory != directory
            or _store.dimension != settings.embedding_dim
            or _store.embedding_model != settings.embedding_model
        ):
            _store = VectorStore(
                directory=directory,
                dimension=settings.embedding_dim,
                embedding_model=settings.embedding_model,
            )
        return _store


def reset_vector_store() -> None:
    global _store
    with _store_lock:
        if _store is not None:
            _store.reset()
        _store = None
