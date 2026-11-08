"""LangGraph workflow for the IVAP agent."""

import json
import logging
import time
from typing import Any, Dict, List

from langgraph.graph import END, START, StateGraph

from app.agents.prompts import SYSTEM_PROMPT, build_context_message
from app.agents.state import AgentState
from app.agents.tools import (
    ToolContext,
    citations_from_result,
    execute_tool,
    openai_tools,
)
from app.core.config import Settings
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

MAX_TOOL_OUTPUT_CHARS = 12000


def _last_assistant_tool_calls(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not messages:
        return []
    last = messages[-1]
    if last.get("role") != "assistant":
        return []
    return last.get("tool_calls") or []


def build_graph(context: ToolContext, settings: Settings, max_steps: int):
    async def prepare(state: AgentState) -> Dict[str, Any]:
        history = list(state.get("messages", []))
        system = {
            "role": "system",
            "content": SYSTEM_PROMPT
            + "\n\n"
            + build_context_message(state.get("task_id"), state.get("image_path")),
        }
        return {
            "messages": [system] + history,
            "step": 0,
            "max_steps": max_steps,
            "tool_calls": [],
            "citations": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "final_answer": "",
            "error": None,
            "requires_confirmation": False,
        }

    async def agent_node(state: AgentState) -> Dict[str, Any]:
        if settings.llm_mock:
            return {
                "final_answer": (
                    "（Mock 模式）当前为开发联调模式，未调用真实 LLM，"
                    "因此没有执行工具编排。请使用真实 LLM 配置进行 P6 验收。"
                )
            }

        messages = list(state["messages"])
        service = LLMService(settings)
        try:
            result = await service.chat_with_tools(
                messages=messages,
                tools=openai_tools(),
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
        finally:
            await service.aclose()

        assistant: Dict[str, Any] = {"role": "assistant", "content": result.content}
        if result.tool_calls:
            assistant["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in result.tool_calls
            ]
        messages.append(assistant)

        usage = dict(state.get("usage") or {})
        usage["prompt_tokens"] = usage.get("prompt_tokens", 0) + result.prompt_tokens
        usage["completion_tokens"] = (
            usage.get("completion_tokens", 0) + result.completion_tokens
        )

        update: Dict[str, Any] = {"messages": messages, "usage": usage}
        if not result.tool_calls:
            update["final_answer"] = result.content
        return update

    async def tools_node(state: AgentState) -> Dict[str, Any]:
        messages = list(state["messages"])
        logs = list(state.get("tool_calls") or [])
        citations = list(state.get("citations") or [])
        current_task_id = state.get("task_id")

        for call in _last_assistant_tool_calls(messages):
            call_id = call.get("id") or ""
            function = call.get("function") or {}
            name = function.get("name") or ""
            raw_arguments = function.get("arguments") or "{}"
            try:
                parsed_arguments = json.loads(raw_arguments)
            except (TypeError, json.JSONDecodeError):
                parsed_arguments = {"_raw": raw_arguments}

            started = time.perf_counter()
            result, error_code = await execute_tool(name, raw_arguments, context)
            duration_ms = int(round((time.perf_counter() - started) * 1000))

            logs.append(
                {
                    "name": name,
                    "arguments": parsed_arguments,
                    "status": "error" if error_code else "success",
                    "duration_ms": duration_ms,
                    "error_code": error_code,
                }
            )

            if error_code is None and name == "search_knowledge_base":
                for item in citations_from_result(result):
                    key = (
                        item.get("document_id"),
                        item.get("page_no"),
                        item.get("chunk_index"),
                    )
                    if key not in {
                        (c.get("document_id"), c.get("page_no"), c.get("chunk_index"))
                        for c in citations
                    }:
                        citations.append(item)

            if error_code is None and name == "detect_image" and result.get("task_id"):
                current_task_id = result["task_id"]
                context.task_id = current_task_id

            content = json.dumps(result, ensure_ascii=False)
            if len(content) > MAX_TOOL_OUTPUT_CHARS:
                content = content[:MAX_TOOL_OUTPUT_CHARS] + "...[truncated]"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": content,
                }
            )

        return {
            "messages": messages,
            "tool_calls": logs,
            "citations": citations,
            "step": int(state.get("step", 0)) + 1,
            "task_id": current_task_id,
        }

    async def finalize(state: AgentState) -> Dict[str, Any]:
        answer = (state.get("final_answer") or "").strip()
        if not answer:
            if state.get("error"):
                answer = f"处理失败：{state['error']}"
            else:
                answer = (
                    "已达到工具调用上限，未能生成最终答案。"
                    "请缩小问题范围后重试。"
                )
        return {"final_answer": answer}

    def route_after_agent(state: AgentState) -> str:
        if state.get("final_answer"):
            return "finalize"
        calls = _last_assistant_tool_calls(state.get("messages", []))
        if calls and int(state.get("step", 0)) < int(state.get("max_steps", max_steps)):
            return "tools"
        return "finalize"

    def route_after_tools(state: AgentState) -> str:
        return "agent"

    builder = StateGraph(AgentState)
    builder.add_node("prepare", prepare)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tools_node)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "agent")
    builder.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "finalize": "finalize"},
    )
    builder.add_edge("tools", "agent")
    builder.add_edge("finalize", END)

    return builder.compile()
