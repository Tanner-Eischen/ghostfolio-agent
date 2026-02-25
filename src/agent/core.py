"""Main Ghostfolio Agent implementation.

This module provides the GhostfolioAgent class - an AI-powered portfolio
assistant that uses LangGraph to provide natural language access to
portfolio analysis, risk assessment, and financial insights.
"""

import time
import uuid
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langsmith import traceable

from src.agent.prompts import SYSTEM_PROMPT
from src.tools import ALL_TOOLS
from src.utils.config import get_settings
from src.utils.logging import get_logger
from src.utils.tracing import configure_langsmith, is_tracing_enabled, TraceContext
from src.verification import VerificationPipeline

logger = get_logger(__name__)


class GhostfolioAgent:
    """AI-powered portfolio assistant for Ghostfolio.

    This agent uses LangGraph to provide natural language access to
    portfolio analysis, risk assessment, and financial insights.

    Features:
    - 5 specialized tools for portfolio analysis
    - Automatic verification of responses
    - Conversation history management
    - Confidence scoring with escalation triggers
    - Full LangSmith tracing and observability

    Example:
        ```python
        agent = GhostfolioAgent()

        # Simple chat
        response = await agent.chat("What's my portfolio worth?")
        print(response)

        # Stateful chat with context
        result = await agent.chat_with_context(
            "How diversified am I?",
            session_id="user-123"
        )
        print(result["message"])
        print(f"Confidence: {result['confidence']}%")
        ```
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        use_verification: bool = True,
        verification_strict_mode: bool = False,
        enable_tracing: bool = True,
    ) -> None:
        """Initialize the Ghostfolio Agent.

        Args:
            model: OpenAI model to use (default: gpt-4o-mini)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            use_verification: Whether to verify responses
            verification_strict_mode: Fail on any verification issue
            enable_tracing: Whether to enable LangSmith tracing
        """
        self.settings = get_settings()
        self.logger = logger
        self.enable_tracing = enable_tracing

        # Configure LangSmith tracing
        if enable_tracing:
            configure_langsmith()

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self.settings.openai_api_key or None,
        )

        # Store tools
        self.tools = ALL_TOOLS
        self.tool_map = {tool.name: tool for tool in self.tools}

        # Create the LangGraph agent
        self.graph = create_agent(
            self.llm,
            self.tools,
            system_prompt=SYSTEM_PROMPT,
            checkpointer=MemorySaver(),
        )

        # Initialize verification pipeline
        self.use_verification = use_verification
        self.verification = VerificationPipeline(
            strict_mode=verification_strict_mode,
        ) if use_verification else None

        # Conversation history storage
        self._conversation_history: dict[str, list[HumanMessage | AIMessage]] = {}

        self.logger.info(
            f"GhostfolioAgent initialized with {len(self.tools)} tools, "
            f"verification={'enabled' if use_verification else 'disabled'}"
        )

    @traceable(name="agent_chat", run_type="chain")
    async def chat(self, message: str) -> str:
        """Send a message to the agent and get a response.

        Args:
            message: User's natural language query

        Returns:
            Agent's response as a string
        """
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        inputs = {"messages": [HumanMessage(content=message)]}

        result = await self.graph.ainvoke(inputs, config)

        # Extract the last AI message
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                return msg.content

        return "I couldn't process your request."

    @traceable(name="agent_chat_with_context", run_type="chain")
    async def chat_with_context(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a message with session context.

        Args:
            message: User's natural language query
            session_id: Session identifier for conversation history
            user_id: Optional user identifier

        Returns:
            Response dict with message, confidence, tool_calls, etc.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        start_time = time.time()

        # Build input messages
        messages: list[BaseMessage] = []
        if session_id in self._conversation_history:
            messages.extend(self._conversation_history[session_id])

        user_message = HumanMessage(content=message)
        messages.append(user_message)

        config = {"configurable": {"thread_id": session_id}}
        inputs = {"messages": messages}

        try:
            result = await self.graph.ainvoke(inputs, config)

            # Extract response
            response_messages = result.get("messages", [])
            response_text = ""
            tool_calls = []
            tool_outputs = []

            for msg in reversed(response_messages):
                if isinstance(msg, AIMessage):
                    response_text = msg.content
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        tool_calls = [
                            {"tool": tc.get("name", ""), "input": tc.get("args", {})}
                            for tc in msg.tool_calls
                        ]
                    break

            # Extract tool outputs
            from langchain_core.messages import ToolMessage
            for msg in response_messages:
                if isinstance(msg, ToolMessage) and hasattr(msg, "content"):
                    try:
                        import json
                        output = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                        tool_outputs.append(output)
                    except (json.JSONDecodeError, TypeError):
                        tool_outputs.append({"raw": msg.content})

            # Run verification
            verification_report = None
            if self.use_verification and self.verification:
                verification_report = await self.verification.verify(
                    response=response_text,
                    tool_outputs=tool_outputs,
                    query=message,
                )

            # Update history
            if session_id not in self._conversation_history:
                self._conversation_history[session_id] = []
            self._conversation_history[session_id].append(user_message)
            self._conversation_history[session_id].append(AIMessage(content=response_text))

            processing_time = time.time() - start_time

            return {
                "message": response_text,
                "session_id": session_id,
                "confidence": verification_report.confidence_score if verification_report else 100.0,
                "confidence_level": verification_report.confidence_level if verification_report else "HIGH",
                "tool_calls": tool_calls,
                "verification_passed": verification_report.passed if verification_report else True,
                "requires_escalation": verification_report.escalation.requires_escalation if verification_report else False,
                "escalation_triggers": verification_report.escalation.triggers if verification_report else [],
                "metadata": {
                    "processing_time_ms": round(processing_time * 1000, 2),
                    "tools_used": len(tool_calls),
                    "tool_names": [tc.get("tool") for tc in tool_calls],
                },
            }

        except Exception as e:
            self.logger.error(f"Chat error: {e}")
            return {
                "message": f"I encountered an error: {str(e)}",
                "session_id": session_id,
                "confidence": 0.0,
                "confidence_level": "VERY_LOW",
                "tool_calls": [],
                "verification_passed": False,
                "requires_escalation": True,
                "escalation_triggers": [f"Error: {str(e)}"],
                "metadata": {
                    "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                    "error": str(e),
                },
            }

    def get_tools(self) -> list[Any]:
        """Get list of available tools."""
        return self.tools

    def get_tool_descriptions(self) -> list[dict[str, str]]:
        """Get descriptions of all available tools."""
        return [{"name": tool.name, "description": tool.description} for tool in self.tools]

    def clear_conversation(self, session_id: str) -> bool:
        """Clear conversation history for a session."""
        if session_id in self._conversation_history:
            del self._conversation_history[session_id]
            return True
        return False


# Singleton instance
_agent_instance: GhostfolioAgent | None = None


def get_agent() -> GhostfolioAgent:
    """Get or create the singleton agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GhostfolioAgent()
    return _agent_instance
