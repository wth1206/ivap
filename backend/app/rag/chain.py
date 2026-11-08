"""RAG answer generation with source citations."""

import logging
from dataclasses import dataclass
from typing import List

from app.core.config import Settings
from app.core.exceptions import AppError
from app.schemas.knowledge import KnowledgeSearchItem
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是无人机遥感与目标检测领域的知识库问答助手。
必须遵守：
1. 只能依据用户提供的资料片段回答，不得使用片段之外的事实。
2. 每个结论后用 [S1]、[S2] 这样的编号标注来源；至少引用一个来源。
3. 如果资料不足以回答，直接说明“知识库中未检索到足够依据”，不要编造。
4. 用中文回答，简洁、专业；不要输出 Markdown 表格。
"""


@dataclass
class RAGAnswer:
    answer: str
    is_mock: bool
    model_name: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int


def build_context(items: List[KnowledgeSearchItem]) -> str:
    parts = []
    for index, item in enumerate(items, start=1):
        location = f"第 {item.page_no} 页" if item.page_no else "无页码（段落/行号见元数据）"
        parts.append(
            f"[S{index}] 文档《{item.document_name}》{location}，片段 {item.chunk_index}\n"
            f"{item.content}"
        )
    return "\n\n".join(parts)


def _mock_answer(items: List[KnowledgeSearchItem]) -> str:
    if not items:
        return "知识库中未检索到足够依据。"
    snippets = "；".join(
        f"[S{index}] {item.content[:80]}" for index, item in enumerate(items[:3], start=1)
    )
    return (
        "（Mock 模式，未调用 LLM）根据检索到的片段："
        f"{snippets}。以上内容仅用于验证引用结构，不能作为真实结论。"
    )


async def answer_question(
    settings: Settings,
    query: str,
    items: List[KnowledgeSearchItem],
) -> RAGAnswer:
    if not items:
        return RAGAnswer(
            answer="知识库中未检索到与该问题相关的内容，无法基于知识库回答。",
            is_mock=settings.llm_mock,
            model_name="none",
            latency_ms=0,
            prompt_tokens=0,
            completion_tokens=0,
        )

    if settings.llm_mock:
        return RAGAnswer(
            answer=_mock_answer(items),
            is_mock=True,
            model_name="llm-mock",
            latency_ms=0,
            prompt_tokens=0,
            completion_tokens=0,
        )

    if not settings.llm_configured:
        raise AppError(
            "LLM_NOT_CONFIGURED",
            "LLM 未配置，无法生成知识库问答",
            503,
        )

    context = build_context(items)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"问题：{query}\n\n资料片段：\n{context}\n\n"
                "请基于上述片段回答，并用 [S1] 等编号标注来源；资料不足时明确说明。"
            ),
        },
    ]
    service = LLMService(settings)
    try:
        result = await service.chat_text(messages, max_tokens=1200, temperature=0.2)
    finally:
        await service.aclose()

    logger.info(
        "RAG answer model=%s latency=%dms sources=%d",
        result.model,
        result.latency_ms,
        len(items),
    )
    return RAGAnswer(
        answer=result.content,
        is_mock=False,
        model_name=result.model,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
