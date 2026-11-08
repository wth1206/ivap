"""OpenAI-compatible LLM client used by the analysis/RAG/Agent layers."""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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


class LLMOutputError(AppError):
    """The upstream call succeeded but did not return usable JSON."""

    def __init__(
        self,
        message: str,
        raw_content: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__("LLM_OUTPUT_INVALID", message, 502, details)
        self.raw_content = raw_content


@dataclass
class LLMJsonResult:
    data: Dict[str, Any]
    model: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    raw_content: str


@dataclass
class LLMTextResult:
    content: str
    model: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: str


@dataclass
class LLMToolResult:
    content: str
    tool_calls: List[ToolCallRequest]
    model: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str


def extract_json(text: str) -> Dict[str, Any]:
    """Extract a JSON object from plain text or a Markdown code fence."""
    if not text or not text.strip():
        raise ValueError("empty response")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            cleaned = "\n".join(lines[1:])
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found")
    parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("JSON root is not an object")
    return parsed


class LLMService:
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_configured:
            raise AppError(
                "LLM_NOT_CONFIGURED",
                "LLM 未配置，请设置 LLM_API_KEY 与 LLM_MODEL",
                503,
            )
        self.settings = settings
        self.model = settings.llm_model
        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            timeout=float(settings.llm_timeout_seconds),
            max_retries=int(settings.llm_max_retries),
        )

    async def aclose(self) -> None:
        await self._client.close()

    async def _create(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ):
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return await self._client.chat.completions.create(**kwargs)

    async def chat_text(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMTextResult:
        """Call the model for plain-text answers (RAG / Agent)."""
        tokens = int(max_tokens or 1200)
        temp = float(
            self.settings.llm_temperature if temperature is None else temperature
        )
        started = time.perf_counter()
        try:
            response = await self._create(messages, tokens, temp, json_mode=False)
        except APITimeoutError as exc:
            raise AppError("LLM_TIMEOUT", "LLM 请求超时", 504) from exc
        except AuthenticationError as exc:
            raise AppError("LLM_AUTH_ERROR", "LLM 鉴权失败，请检查 API Key", 502) from exc
        except RateLimitError as exc:
            raise AppError("LLM_RATE_LIMITED", "LLM 限流，请稍后重试", 503) from exc
        except BadRequestError as exc:
            raise AppError(
                "LLM_UPSTREAM_ERROR",
                "LLM 请求参数被上游拒绝",
                502,
                {"reason": str(exc)[:300]},
            ) from exc
        except APIError as exc:
            raise AppError(
                "LLM_UPSTREAM_ERROR",
                "LLM 上游调用失败",
                502,
                {"reason": str(exc)[:300]},
            ) from exc

        latency_ms = int(round((time.perf_counter() - started) * 1000))
        choice = response.choices[0]
        content = choice.message.content or ""
        if not content.strip():
            raise LLMOutputError(
                "LLM 未返回文本内容",
                raw_content=content,
                details={"finish_reason": choice.finish_reason},
            )
        if choice.finish_reason == "length":
            raise LLMOutputError(
                "LLM 回答被截断，请减小上下文或增大 max_tokens",
                raw_content=content,
                details={"finish_reason": choice.finish_reason},
            )

        usage = response.usage
        prompt_tokens = int(usage.prompt_tokens) if usage else 0
        completion_tokens = int(usage.completion_tokens) if usage else 0
        logger.info(
            "LLM text call model=%s latency=%dms prompt_tokens=%d completion_tokens=%d",
            response.model,
            latency_ms,
            prompt_tokens,
            completion_tokens,
        )
        return LLMTextResult(
            content=content.strip(),
            model=response.model or self.model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tool_choice: str = "auto",
    ) -> LLMToolResult:
        """Call the model with OpenAI-style function tools."""
        tokens = int(max_tokens or self.settings.llm_max_tokens)
        temp = float(
            self.settings.llm_temperature if temperature is None else temperature
        )
        started = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=tokens,
                temperature=temp,
            )
        except APITimeoutError as exc:
            raise AppError("LLM_TIMEOUT", "LLM 请求超时", 504) from exc
        except AuthenticationError as exc:
            raise AppError("LLM_AUTH_ERROR", "LLM 鉴权失败，请检查 API Key", 502) from exc
        except RateLimitError as exc:
            raise AppError("LLM_RATE_LIMITED", "LLM 限流，请稍后重试", 503) from exc
        except BadRequestError as exc:
            raise AppError(
                "LLM_TOOL_CALLING_UNSUPPORTED",
                "上游模型不支持工具调用或参数被拒绝",
                502,
                {"reason": str(exc)[:300]},
            ) from exc
        except APIError as exc:
            raise AppError(
                "LLM_UPSTREAM_ERROR",
                "LLM 上游调用失败",
                502,
                {"reason": str(exc)[:300]},
            ) from exc

        latency_ms = int(round((time.perf_counter() - started) * 1000))
        choice = response.choices[0]
        message = choice.message
        content = message.content or ""
        calls = [
            ToolCallRequest(
                id=call.id,
                name=call.function.name,
                arguments=call.function.arguments or "{}",
            )
            for call in (message.tool_calls or [])
        ]
        if not content.strip() and not calls:
            raise LLMOutputError(
                "LLM 既没有返回文本也没有工具调用",
                raw_content=content,
                details={"finish_reason": choice.finish_reason},
            )
        if choice.finish_reason == "length" and not calls:
            raise LLMOutputError(
                "LLM 输出被截断，请增大 LLM_MAX_TOKENS",
                raw_content=content,
                details={"finish_reason": choice.finish_reason},
            )

        usage = response.usage
        prompt_tokens = int(usage.prompt_tokens) if usage else 0
        completion_tokens = int(usage.completion_tokens) if usage else 0
        logger.info(
            "LLM tool call model=%s latency=%dms tools=%d prompt_tokens=%d completion_tokens=%d",
            response.model,
            latency_ms,
            len(calls),
            prompt_tokens,
            completion_tokens,
        )
        return LLMToolResult(
            content=content.strip(),
            tool_calls=calls,
            model=response.model or self.model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=choice.finish_reason or "",
        )

    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMJsonResult:
        """Call the model in JSON mode and parse the returned object."""
        tokens = int(max_tokens or self.settings.llm_max_tokens)
        temp = float(
            self.settings.llm_temperature if temperature is None else temperature
        )
        started = time.perf_counter()

        try:
            try:
                response = await self._create(messages, tokens, temp, json_mode=True)
            except BadRequestError as exc:
                # Some compatible gateways reject response_format; fall back to
                # plain output and let the parser find the JSON object.
                if "response_format" not in str(exc).lower():
                    raise
                logger.warning("Gateway rejected response_format; retrying plain JSON prompt")
                response = await self._create(messages, tokens, temp, json_mode=False)
        except APITimeoutError as exc:
            raise AppError("LLM_TIMEOUT", "LLM 请求超时", 504) from exc
        except AuthenticationError as exc:
            raise AppError("LLM_AUTH_ERROR", "LLM 鉴权失败，请检查 API Key", 502) from exc
        except RateLimitError as exc:
            raise AppError("LLM_RATE_LIMITED", "LLM 限流，请稍后重试", 503) from exc
        except BadRequestError as exc:
            raise AppError(
                "LLM_UPSTREAM_ERROR",
                "LLM 请求参数被上游拒绝",
                502,
                {"reason": str(exc)[:300]},
            ) from exc
        except APIError as exc:
            raise AppError(
                "LLM_UPSTREAM_ERROR",
                "LLM 上游调用失败",
                502,
                {"reason": str(exc)[:300]},
            ) from exc

        latency_ms = int(round((time.perf_counter() - started) * 1000))
        choice = response.choices[0]
        content = choice.message.content or ""
        finish_reason = choice.finish_reason
        usage = response.usage
        prompt_tokens = int(usage.prompt_tokens) if usage else 0
        completion_tokens = int(usage.completion_tokens) if usage else 0

        details = {
            "finish_reason": finish_reason,
            "completion_tokens": completion_tokens,
        }
        if not content.strip():
            raise LLMOutputError(
                "LLM 未返回文本内容（可能是 token 预算不足或触发内容过滤）",
                raw_content=content,
                details=details,
            )
        if finish_reason == "length":
            raise LLMOutputError(
                "LLM 输出被截断（finish_reason=length），请增大 LLM_MAX_TOKENS",
                raw_content=content,
                details=details,
            )

        try:
            data = extract_json(content)
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMOutputError(
                "LLM 返回内容不是合法 JSON",
                raw_content=content,
                details={**details, "parse_error": str(exc)[:200]},
            ) from exc

        logger.info(
            "LLM json call model=%s latency=%dms prompt_tokens=%d completion_tokens=%d",
            response.model,
            latency_ms,
            prompt_tokens,
            completion_tokens,
        )
        return LLMJsonResult(
            data=data,
            model=response.model or self.model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            raw_content=content,
        )
