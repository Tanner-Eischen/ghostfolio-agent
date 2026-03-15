"""LangGraph state management for the agent."""

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State schema for the Ghostfolio Agent."""

    # Conversation messages (accumulated)
    messages: Annotated[list[BaseMessage], add_messages]

    # Current tool calls being processed
    current_tool_calls: list[dict[str, Any]]

    # Verification results
    verification_results: dict[str, Any]

    # Confidence score (0-100)
    confidence: float

    # Session metadata
    session_id: str
    user_id: str | None

    # Error tracking
    errors: list[str]

    # Performance metrics
    tool_execution_times: dict[str, float]


def create_initial_state(session_id: str, user_id: str | None = None) -> AgentState:
    """Create an initial state for a new conversation."""
    return AgentState(
        messages=[],
        current_tool_calls=[],
        verification_results={},
        confidence=0.0,
        session_id=session_id,
        user_id=user_id,
        errors=[],
        tool_execution_times={},
    )
