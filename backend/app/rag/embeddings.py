"""Embedding providers: OpenAI-compatible API or deterministic mock."""

import hashlib
import logging
import re
from typing import List

import numpy as np
from openai import (
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from app.core.config import Settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = settings.embedding_provider
        self.model = settings.embedding_model
        self.dimension = settings.embedding_dim
        self.batch_size = settings.embedding_batch_size
        self._client = None

        if self.provider == "openai":
            api_key = settings.embedding_api_key_value
            if not api_key:
                raise AppError(
                    "EMBEDDING_NOT_CONFIGURED",
                    "Embedding 未配置 API Key",
                    503,
                )
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.embedding_base_url_value,
                timeout=float(settings.llm_timeout_seconds),
                max_retries=int(settings.llm_max_retries),
            )
        elif self.provider == "mock":
            self._client = None
        else:
            raise AppError(
                "EMBEDDING_PROVIDER_UNSUPPORTED",
                "本地 Embedding 尚未实现，请使用 openai 或 mock",
                503,
                {"provider": self.provider},
            )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        array = np.asarray(vectors, dtype="float32")
        norms = np.linalg.norm(array, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return array / norms

    def _mock_vector(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype="float32")
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            tokens = [text or "empty"]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            position = int.from_bytes(digest[:8], "little") % self.dimension
            vector[position] += 1.0
        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        return vector

    async def _embed_openai(self, texts: List[str]) -> np.ndarray:
        assert self._client is not None
        vectors = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            try:
                response = await self._client.embeddings.create(
                    model=self.model,
                    input=batch,
                )
            except APITimeoutError as exc:
                raise AppError("EMBEDDING_TIMEOUT", "Embedding 请求超时", 504) from exc
            except AuthenticationError as exc:
                raise AppError("EMBEDDING_AUTH_ERROR", "Embedding 鉴权失败", 502) from exc
            except RateLimitError as exc:
                raise AppError("EMBEDDING_RATE_LIMITED", "Embedding 限流", 503) from exc
            except BadRequestError as exc:
                raise AppError(
                    "EMBEDDING_UPSTREAM_ERROR",
                    "Embedding 请求被上游拒绝",
                    502,
                    {"reason": str(exc)[:300]},
                ) from exc
            except APIError as exc:
                raise AppError(
                    "EMBEDDING_UPSTREAM_ERROR",
                    "Embedding 上游调用失败",
                    502,
                    {"reason": str(exc)[:300]},
                ) from exc

            ordered = sorted(response.data, key=lambda item: item.index)
            if len(ordered) != len(batch):
                raise AppError("EMBEDDING_UPSTREAM_ERROR", "Embedding 返回数量不匹配", 502)
            vectors.extend([item.embedding for item in ordered])

        array = np.asarray(vectors, dtype="float32")
        if array.ndim != 2 or array.shape[1] != self.dimension:
            raise AppError(
                "EMBEDDING_DIM_MISMATCH",
                "Embedding 维度与 EMBEDDING_DIM 不一致",
                502,
                {
                    "expected": self.dimension,
                    "actual": int(array.shape[1]) if array.ndim == 2 else None,
                    "model": self.model,
                },
            )
        return self._normalize(array)

    async def embed_documents(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype="float32")
        if self.provider == "mock":
            return self._normalize(
                np.stack([self._mock_vector(text) for text in texts])
            )
        return await self._embed_openai(texts)

    async def embed_query(self, text: str) -> np.ndarray:
        vectors = await self.embed_documents([text])
        return vectors[0]
