"""LangGraph agent state."""

from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    messages: List[Dict[str, Any]]
    conversation_id: str
    user_id: Optional[int]
    task_id: Optional[str]
    image_path: Optional[str]
    step: int
    max_steps: int
    tool_calls: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    usage: Dict[str, int]
    final_answer: str
    error: Optional[str]
    requires_confirmation: bool
