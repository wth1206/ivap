"""Agent runner with timeout and result normalisation."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agents.graph import build_graph
from app.agents.tools import ToolContext
from app.core.config import Settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    answer: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    requires_confirmation: bool = False


class AgentRunner:
    def __init__(self, settings: Settings, context: ToolContext) -> None:
        self.settings = settings
        self.context = context
        self.graph = build_graph(context, settings, settings.agent_max_steps)

    async def run(
        self,
        history: List[Dict[str, Any]],
        task_id: Optional[str] = None,
        image_path: Optional[str] = None,
    ) -> AgentResult:
        initial = {
            "messages": history,
            "conversation_id": self.context.conversation_id,
            "user_id": self.context.user_id,
            "task_id": task_id or self.context.task_id,
            "image_path": image_path or self.context.image_path,
        }
        try:
            state = await asyncio.wait_for(
                self.graph.ainvoke(initial),
                timeout=float(self.settings.agent_timeout_seconds),
            )
        except asyncio.TimeoutError as exc:
            raise AppError(
                "AGENT_TIMEOUT",
                "Agent 执行超时，请稍后重试或缩小问题范围",
                504,
            ) from exc
        except AppError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Agent execution failed")
            raise AppError(
                "AGENT_FAILED",
                "Agent 执行失败",
                502,
                {"reason": str(exc)[:300]},
            ) from exc

        return AgentResult(
            answer=str(state.get("final_answer") or "").strip(),
            tool_calls=list(state.get("tool_calls") or []),
            citations=list(state.get("citations") or []),
            usage=dict(state.get("usage") or {}),
            requires_confirmation=bool(state.get("requires_confirmation")),
        )
