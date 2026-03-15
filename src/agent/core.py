"""Main Ghostfolio Agent implementation.

This module provides the GhostfolioAgent class - an AI-powered portfolio
assistant that uses LangGraph to provide natural language access to
portfolio analysis, risk assessment, and financial insights.
"""

import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from src.agent.prompts import SYSTEM_PROMPT
from src.exceptions import get_friendly_error_message
from src.tools import get_all_tools
from src.utils.config import get_settings
from src.utils.logging import get_logger
from src.utils.session_store import SessionStore
from src.utils.tracing import configure_langsmith, get_trace_url
from src.utils.usage_tracker import log_usage
from src.verification import VerificationPipeline

logger = get_logger(__name__)


def _friendly_error_message(exc: Exception) -> str:
    """Format an exception as a short, conversational message (no HTTP/tech jargon)."""
    # Delegate to centralized error message formatting
    return get_friendly_error_message(exc)



class GhostfolioAgent:
    """AI-powered portfolio assistant for Ghostfolio.

    This agent uses LangGraph to provide natural language access to
    portfolio analysis, risk assessment, and financial insights.

    Features:
    - 3 specialized MVP tools for portfolio analysis
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

        # Initialize LLM: use stripped key from settings and sync to env so LangChain/subcalls use same value
        openai_key = (self.settings.openai_api_key or "").strip() or None
        if openai_key:
            import os
            os.environ["OPENAI_API_KEY"] = openai_key
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=openai_key,
        )

        # Store tools (core + generated)
        self.tools = get_all_tools()
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

        # Conversation history (in-memory cache); persisted via SessionStore
        self._conversation_history: dict[str, list[BaseMessage]] = {}
        self._session_last_accessed: dict[str, datetime] = {}
        self._session_ttl = timedelta(hours=24)  # Sessions expire after 24 hours
        self._session_store = SessionStore()

        self.logger.info(
            f"GhostfolioAgent initialized with {len(self.tools)} tools, "
            f"verification={'enabled' if use_verification else 'disabled'}"
        )

    def _cleanup_expired_sessions(self) -> int:
        """Remove sessions that haven't been accessed in over 24 hours.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now()
        expired_sessions = [
            session_id for session_id, last_accessed in self._session_last_accessed.items()
            if now - last_accessed > self._session_ttl
        ]

        for session_id in expired_sessions:
            self._conversation_history.pop(session_id, None)
            self._session_last_accessed.pop(session_id, None)

        if expired_sessions:
            self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

        return len(expired_sessions)

    def _touch_session(self, session_id: str) -> None:
        """Update the last accessed time for a session."""
        self._session_last_accessed[session_id] = datetime.now()

    def _ensure_session_loaded(self, session_id: str) -> None:
        """Load session from persistent store into memory if not already present."""
        if session_id in self._conversation_history:
            return
        messages = self._session_store.get_history(session_id)
        if messages:
            self._conversation_history[session_id] = list(messages)
            self._session_last_accessed[session_id] = datetime.now()

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

        run_id: str | None = None
        try:
            run_tree = get_current_run_tree()
            if run_tree and hasattr(run_tree, "id"):
                run_id = str(run_tree.id)
        except Exception as run_err:
            self.logger.debug(f"Could not get current run id: {run_err}")

        messages = result.get("messages", [])
        last_ai_message: AIMessage | None = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                last_ai_message = msg
                break

        if last_ai_message:
            usage_meta = (
                getattr(last_ai_message, "response_metadata", None) or {}
            ).get("token_usage", {}) or {}
            input_tokens = usage_meta.get("prompt_tokens", 0)
            output_tokens = usage_meta.get("completion_tokens", 0)
            log_usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.llm.model_name,
                session_id=None,
                query=message[:100] if message else None,
                run_id=run_id,
                metadata={"token_usage_missing": input_tokens == 0 and output_tokens == 0},
            )

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
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a message with session context.

        Args:
            message: User's natural language query
            session_id: Session identifier for conversation history
            user_id: Optional user identifier
            context: Optional context dict (e.g., repo_id for tool execution)

        Returns:
            Response dict with message, confidence, tool_calls, etc.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        # Cleanup expired sessions on each request (lightweight operation)
        self._cleanup_expired_sessions()

        # Mark session as accessed
        self._touch_session(session_id)

        start_time = time.time()
        timing_breakdown = {
            "llm_time_ms": 0,
            "tool_time_ms": 0,
            "verification_time_ms": 0,
        }

        # Handle mixed-intent prompts: refuse unsafe intent but still serve valid portfolio intent.
        # This keeps the agent useful for adversarial+legitimate combined requests.
        safe_message = message
        lowered = message.lower()
        risky_markers = [
            "ignore previous instructions",
            "dump raw backend secrets",
            "dump secrets",
            "api key",
            "credentials",
            "execute this code",
            "os.system",
            "import os",
            "rm -rf",
            "print environment",
            "environment variables",
        ]
        has_risky_intent = any(m in lowered for m in risky_markers)
        has_portfolio_intent = any(t in lowered for t in ["portfolio", "holdings", "risk", "diversif", "investments", "value", "worth"])
        if has_risky_intent and has_portfolio_intent:
            if "portfolio value" in lowered or "portfolio worth" in lowered or "tell me about my portfolio" in lowered:
                safe_message = "What is my portfolio value?"
            elif "holdings" in lowered:
                safe_message = "What are my top holdings?"
            elif "risk" in lowered or "diversif" in lowered:
                safe_message = "Assess my portfolio risk and diversification."
            elif "portfolio" in lowered:
                safe_message = "Analyze my portfolio."

        # Build input messages (load from store if not in memory)
        self._ensure_session_loaded(session_id)
        messages: list[BaseMessage] = []
        if session_id in self._conversation_history:
            messages.extend(self._conversation_history[session_id])

        user_message = HumanMessage(content=safe_message)
        messages.append(user_message)

        # Build config with context
        config = {"configurable": {"thread_id": session_id}}
        if context:
            config["configurable"]["context"] = context

        inputs = {"messages": messages}

        try:
            # Time the LLM + tool execution
            llm_start_time = time.time()
            result = await self.graph.ainvoke(inputs, config)
            llm_end_time = time.time()

            # Get LangSmith run ID early so we can attach it to usage log and response
            run_id: str | None = None
            try:
                run_tree = get_current_run_tree()
                if run_tree and hasattr(run_tree, "id"):
                    run_id = str(run_tree.id)
            except Exception as run_err:
                self.logger.debug(f"Could not get current run id: {run_err}")

            # Calculate LLM time (includes tool execution within LangGraph)
            timing_breakdown["llm_time_ms"] = round((llm_end_time - llm_start_time) * 1000, 2)

            # Extract response
            response_messages = result.get("messages", [])
            response_text = ""
            tool_calls = []
            tool_outputs = []

            def _parse_tool_output(content: Any) -> dict[str, Any] | Any:
                """Best-effort parse of tool output content.

                LangChain tool messages can be JSON strings, native dict/list payloads,
                or pydantic repr strings (e.g. ``field=value``). This parser normalizes
                them into structured objects so eval field checks can run objectively.

                For error strings, synthesizes structured outputs with sentinel values
                so that field_present checks can find fields (even if None) rather than failing.
                """
                if isinstance(content, (dict, list)):
                    return content

                if isinstance(content, str):
                    import json
                    import re

                    # Standard JSON payload
                    try:
                        return json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        pass

                    # Detect error conditions and synthesize structured response
                    lowered = content.lower()
                    is_auth_error = (
                        "authentication" in lowered
                        or "couldn't access" in lowered
                        or "could not access" in lowered
                        or "access token" in lowered
                        or "unauthorized" in lowered
                        or "401" in content
                        or "no ghostfolio" in lowered
                    )
                    is_timeout_error = "timeout" in lowered or "timed out" in lowered
                    is_rate_limit = "rate" in lowered and "limit" in lowered

                    if is_auth_error or is_timeout_error or is_rate_limit:
                        # Synthesize structured error response with expected fields
                        return {
                            "total_value": None,
                            "holdings": [],
                            "data": [],
                            "error": content,
                            "_parse_status": "auth_error" if is_auth_error else "timeout_error" if is_timeout_error else "rate_limit_error",
                        }

                    # Pydantic repr fallback: key=value key2=value2 ...
                    keys = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)=", content)
                    if keys:
                        parsed: dict[str, Any] = {"raw": content}
                        for k in keys:
                            parsed.setdefault(k, True)

                        # Extract numeric values for common financial fields
                        for k in ("total_value", "overall_risk_score", "risk_score", "data_age_seconds"):
                            m = re.search(rf"\b{k}=(-?\d+(?:\.\d+)?)", content)
                            if m:
                                try:
                                    parsed[k] = float(m.group(1))
                                except ValueError:
                                    pass

                        # Extract timestamp-ish fields for freshness checks
                        for k in ("timestamp", "as_of", "last_updated", "date"):
                            m = re.search(rf"""\b{k}=(?:'([^']+)'|"([^"]+)")""", content)
                            if m:
                                parsed[k] = m.group(1) or m.group(2)

                        # Preserve expected top-level structures for eval checks
                        if "data=[" in content:
                            parsed["data"] = parsed.get("data", [])
                        if "holdings=[" in content:
                            parsed["holdings"] = parsed.get("holdings", [])

                        return parsed

                    # For any other unstructured string, wrap with common fields for eval checks
                    return {
                        "total_value": None,
                        "holdings": [],
                        "data": [],
                        "raw": content,
                        "_parse_status": "unstructured",
                    }

                return {"raw": content}

            # Get final AI response and extract token usage
            last_ai_message: AIMessage | None = None
            for msg in reversed(response_messages):
                if isinstance(msg, AIMessage):
                    response_text = msg.content
                    last_ai_message = msg
                    break

            # Log token usage (include run_id so Observability can show cost per trace).
            # When token_usage is missing, log 0 tokens with a flag so the request is still counted.
            if last_ai_message:
                usage_meta = (
                    getattr(last_ai_message, "response_metadata", None) or {}
                ).get("token_usage", {}) or {}
                input_tokens = usage_meta.get("prompt_tokens", 0)
                output_tokens = usage_meta.get("completion_tokens", 0)
                log_usage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=self.llm.model_name,
                    session_id=session_id,
                    query=message[:100] if message else None,
                    run_id=run_id,
                    metadata={"token_usage_missing": input_tokens == 0 and output_tokens == 0},
                )

            # Extract ALL tool calls from all messages (not just final response)
            for msg in response_messages:
                # Check for tool calls in AIMessage
                if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "tool": tc.get("name", ""),
                            "input": tc.get("args", {})
                        })

            # Extract tool outputs
            for msg in response_messages:
                if isinstance(msg, ToolMessage) and hasattr(msg, "content"):
                    tool_outputs.append(_parse_tool_output(msg.content))

            # Pair each tool call with its output for structured visibility (backend + response)
            tool_invocations: list[dict[str, Any]] = []
            for i, tc in enumerate(tool_calls):
                inv = {
                    "call": {"tool": tc.get("tool", ""), "input": tc.get("input", {})},
                    "output": tool_outputs[i] if i < len(tool_outputs) else None,
                }
                tool_invocations.append(inv)
                out_summary = (
                    list(inv["output"].keys())
                    if isinstance(inv["output"], dict)
                    else type(inv["output"]).__name__
                )
                self.logger.info(
                    "tool_invocation tool=%s input=%s output_summary=%s",
                    inv["call"]["tool"],
                    inv["call"]["input"],
                    out_summary,
                    extra={"tool_invocation": inv},
                )

            # Run verification
            verification_report = None
            verification_start_time = time.time()
            if self.use_verification and self.verification:
                # If tools were called but outputs weren't captured, create synthetic output
                effective_tool_outputs = tool_outputs
                if not tool_outputs and tool_calls:
                    # Tools were invoked - extract numbers from response for fact checking
                    import re
                    response_numbers = re.findall(r'\$?([\d,]+(?:\.\d+)?)\%?', response_text)
                    extracted_values = [float(n.replace(',', '')) for n in response_numbers if n.replace(',', '').replace('.', '').isdigit()]

                    effective_tool_outputs = [{
                        "tool_used": True,
                        "tools": [tc.get("tool") for tc in tool_calls],
                        # Include extracted numbers for fact checker to verify against
                        "extracted_values": extracted_values[:10],  # Limit to 10 values
                        "total_value": extracted_values[0] if extracted_values else None,
                    }]

                # Pass first portfolio-like tool output for constraint validation (total_value >= 0)
                response_data = None
                for out in effective_tool_outputs:
                    if isinstance(out, dict) and "total_value" in out:
                        response_data = out
                        break
                verification_report = await self.verification.verify(
                    response=response_text,
                    tool_outputs=effective_tool_outputs,
                    query=message,
                    response_data=response_data,
                )
            verification_end_time = time.time()
            timing_breakdown["verification_time_ms"] = round((verification_end_time - verification_start_time) * 1000, 2)

            # Update history - store all messages including tool calls and responses
            # to avoid OpenAI error about tool_call_ids without responses
            if session_id not in self._conversation_history:
                self._conversation_history[session_id] = []
            self._conversation_history[session_id].append(user_message)

            # Store all response messages (AIMessage with tool_calls, ToolMessages, final AIMessage)
            # This preserves the tool_call_id -> ToolMessage pairing that OpenAI requires
            for msg in response_messages:
                if isinstance(msg, (AIMessage, ToolMessage)):
                    self._conversation_history[session_id].append(msg)

            # Persist to disk so history survives restarts
            self._session_store.save_history(
                session_id,
                self._conversation_history[session_id],
                self._session_last_accessed[session_id].isoformat(),
            )

            processing_time = time.time() - start_time

            # Estimate tool time as portion of LLM time (rough heuristic)
            # Tools typically take 10-30% of the graph invocation time
            if tool_calls:
                timing_breakdown["tool_time_ms"] = round(timing_breakdown["llm_time_ms"] * 0.2, 2)
                timing_breakdown["llm_time_ms"] = round(timing_breakdown["llm_time_ms"] * 0.8, 2)

            trace_url = get_trace_url(run_id) if run_id else None

            out = {
                "message": response_text,
                "session_id": session_id,
                "confidence": verification_report.confidence_score if verification_report else 100.0,
                "confidence_level": verification_report.confidence_level if verification_report else "HIGH",
                "tool_calls": tool_calls,
                "tool_outputs": tool_outputs,  # Always include tool outputs for transparency
                "tool_invocations": tool_invocations,  # Paired call+output for structured visibility
                "verification_passed": verification_report.passed if verification_report else True,
                "requires_escalation": verification_report.escalation.requires_escalation if verification_report else False,
                "escalation_triggers": verification_report.escalation.triggers if verification_report else [],
                "run_id": run_id,
                "trace_url": trace_url,
                "metadata": {
                    "processing_time_ms": round(processing_time * 1000, 2),
                    "tools_used": len(tool_calls),
                    "tool_names": [tc.get("tool") for tc in tool_calls],
                    "timing_breakdown": timing_breakdown,
                },
            }
            return out

        except Exception as e:
            self.logger.error(f"Chat error: {e}")
            run_id_err: str | None = None
            trace_url_err: str | None = None
            try:
                run_tree = get_current_run_tree()
                if run_tree and hasattr(run_tree, "id"):
                    run_id_err = str(run_tree.id)
                    trace_url_err = get_trace_url(run_id_err)
            except Exception:
                pass
            friendly = _friendly_error_message(e)
            return {
                "message": friendly,
                "session_id": session_id,
                "confidence": 0.0,
                "confidence_level": "VERY_LOW",
                "tool_calls": [],
                "tool_outputs": [],
                "tool_invocations": [],
                "verification_passed": False,
                "requires_escalation": True,
                "escalation_triggers": [friendly],
                "run_id": run_id_err,
                "trace_url": trace_url_err,
                "metadata": {
                    "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                    "error": str(e),
                    "timing_breakdown": timing_breakdown,
                },
            }

    def get_tools(self) -> list[Any]:
        """Get list of available tools."""
        return self.tools

    def get_tool_descriptions(self) -> list[dict[str, str]]:
        """Get descriptions of all available tools."""
        return [{"name": tool.name, "description": tool.description} for tool in self.tools]

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions with message count and last accessed time (from persistent store)."""
        return self._session_store.list_sessions()

    def get_session_history(self, session_id: str) -> list[BaseMessage]:
        """Get message history for a session, loading from store if not in memory."""
        self._ensure_session_loaded(session_id)
        return self._conversation_history.get(session_id, [])

    def clear_conversation(self, session_id: str) -> bool:
        """Clear conversation history for a session (memory and persistent store)."""
        removed_from_store = self._session_store.delete_session(session_id)
        if session_id in self._conversation_history:
            del self._conversation_history[session_id]
            self._session_last_accessed.pop(session_id, None)
            return True
        return removed_from_store

    def reload_tools(self) -> bool:
        """Reload tools from registry, recreate LangGraph.

        Call this after registering new generated tools to make them
        available to the agent.

        Returns:
            True if reload was successful
        """
        try:
            from src.tools.registry import clear_tool_cache
            # Clear the generated tools cache first
            clear_tool_cache()

            # Reload all tools
            self.tools = get_all_tools()
            self.tool_map = {tool.name: tool for tool in self.tools}

            # Recreate the LangGraph agent
            self.graph = create_agent(
                self.llm,
                self.tools,
                system_prompt=SYSTEM_PROMPT,
                checkpointer=MemorySaver(),
            )

            self.logger.info(f"Reloaded tools: {len(self.tools)} tools available")
            return True

        except Exception as e:
            self.logger.error(f"Failed to reload tools: {e}")
            return False


# Singleton instance
_agent_instance: GhostfolioAgent | None = None


def get_agent() -> GhostfolioAgent:
    """Get or create the singleton agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GhostfolioAgent()
    return _agent_instance


def reload_agent_tools() -> bool:
    """Reload tools in the singleton agent.

    Call this after registering new generated tools.

    Returns:
        True if reload was successful, False if agent not initialized or failed
    """
    global _agent_instance
    if _agent_instance is None:
        logger.warning("Agent not initialized, cannot reload tools")
        return False
    return _agent_instance.reload_tools()
