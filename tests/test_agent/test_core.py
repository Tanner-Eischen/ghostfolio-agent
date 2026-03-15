"""Tests for the GhostfolioAgent core functionality."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.core import GhostfolioAgent, get_agent
from src.agent.prompts import SYSTEM_PROMPT, TOOL_SELECTION_PROMPT, VERIFICATION_PROMPT
from src.agent.state import create_initial_state


class TestAgentState:
    """Tests for AgentState and state management."""

    def test_create_initial_state_defaults(self):
        """Test creating initial state with default values."""
        state = create_initial_state("test-session")

        assert state["session_id"] == "test-session"
        assert state["user_id"] is None
        assert state["messages"] == []
        assert state["current_tool_calls"] == []
        assert state["verification_results"] == {}
        assert state["confidence"] == 0.0
        assert state["errors"] == []
        assert state["tool_execution_times"] == {}

    def test_create_initial_state_with_user_id(self):
        """Test creating initial state with user ID."""
        state = create_initial_state("test-session", user_id="user-123")

        assert state["session_id"] == "test-session"
        assert state["user_id"] == "user-123"

    def test_state_message_accumulation(self):
        """Test that messages can be added to state."""
        state = create_initial_state("test-session")

        # Add messages
        state["messages"].append(HumanMessage(content="Hello"))
        state["messages"].append(AIMessage(content="Hi there!"))

        assert len(state["messages"]) == 2
        assert isinstance(state["messages"][0], HumanMessage)
        assert isinstance(state["messages"][1], AIMessage)


class TestGhostfolioAgentInit:
    """Tests for GhostfolioAgent initialization."""

    def test_init_default_settings(self, mock_settings):
        """Test agent initialization with default settings."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                assert agent.tools is not None
                assert len(agent.tools) == 7
                assert agent.use_verification is True
                assert agent.verification is not None

    def test_init_custom_model(self, mock_settings):
        """Test agent initialization with custom model."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI") as mock_llm:
                agent = GhostfolioAgent(model="claude-3-opus-20240229")

                mock_llm.assert_called_once()
                call_kwargs = mock_llm.call_args[1]
                assert call_kwargs["model"] == "claude-3-opus-20240229"

    def test_init_verification_disabled(self, mock_settings):
        """Test agent initialization with verification disabled."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent(use_verification=False)

                assert agent.use_verification is False
                assert agent.verification is None

    def test_init_strict_verification(self, mock_settings):
        """Test agent initialization with strict verification mode."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent(verification_strict_mode=True)

                assert agent.verification.strict_mode is True


class TestGhostfolioAgentTools:
    """Tests for tool-related functionality."""

    def test_get_tools(self, mock_settings):
        """Test getting list of available tools."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                tools = agent.get_tools()
                assert len(tools) == 7

                tool_names = {t.name for t in tools}
                expected_names = {
                    "portfolio_analysis",
                    "transaction_categorize",
                    "risk_assessment",
                    "market_data_lookup",
                    "compliance_check",
                    "price_history",
                    "trending_crypto",
                }
                assert tool_names == expected_names

    def test_get_tool_descriptions(self, mock_settings):
        """Test getting tool descriptions."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                descriptions = agent.get_tool_descriptions()
                assert len(descriptions) == 7

                for desc in descriptions:
                    assert "name" in desc
                    assert "description" in desc

    def test_tool_map_created(self, mock_settings):
        """Test that tool map is created correctly."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                assert "portfolio_analysis" in agent.tool_map
                assert "risk_assessment" in agent.tool_map
                assert len(agent.tool_map) == 7


class TestGhostfolioAgentChat:
    """Tests for chat functionality."""

    @pytest.mark.asyncio
    async def test_chat_simple(self, mock_settings):
        """Test simple chat without context."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                # Mock the graph execution
                agent.graph.ainvoke = AsyncMock(
                    return_value={"messages": [AIMessage(content="Your portfolio is worth $100,000.")]}
                )

                response = await agent.chat("What's my portfolio worth?")

                assert response == "Your portfolio is worth $100,000."
                agent.graph.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_with_context(self, mock_settings):
        """Test chat with session context."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                # Mock the graph execution
                mock_state = {
                    "messages": [AIMessage(content="Your portfolio is worth $100,000.")],
                    "current_tool_calls": [{"tool": "portfolio_analysis", "input": {}}],
                    "_tool_outputs": [{"total_value": 100000}],
                    "errors": [],
                }

                agent.graph.ainvoke = AsyncMock(return_value=mock_state)

                result = await agent.chat_with_context(
                    "What's my portfolio worth?",
                    session_id="test-session"
                )

                assert "message" in result
                assert "confidence" in result
                assert "session_id" in result
                assert result["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_chat_with_context_generates_session_id(self, mock_settings):
        """Test that session ID is generated if not provided."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                mock_state = {
                    "messages": [AIMessage(content="Test response")],
                    "current_tool_calls": [],
                    "_tool_outputs": [],
                    "errors": [],
                }

                agent.graph.ainvoke = AsyncMock(return_value=mock_state)

                result = await agent.chat_with_context("Hello")

                assert "session_id" in result
                assert result["session_id"] is not None

    @pytest.mark.asyncio
    async def test_chat_error_handling(self, mock_settings):
        """Test error handling in chat."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                agent.graph.ainvoke = AsyncMock(side_effect=Exception("Test error"))

                result = await agent.chat_with_context(
                    "What's my portfolio?",
                    session_id="test-session"
                )

                assert "error" in result["message"].lower() or "error" in result["metadata"]
                assert result["requires_escalation"] is True
                assert result["confidence"] == 0.0


class TestConversationHistory:
    """Tests for conversation history management."""

    def test_get_empty_history(self, mock_settings):
        """Test getting history for non-existent session."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                history = agent.get_session_history("non-existent")

                assert history == []

    def test_conversation_history_stored(self, mock_settings):
        """Test that conversation history is stored."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                # Manually add history
                agent._conversation_history["test-session"] = [
                    HumanMessage(content="Hello"),
                    AIMessage(content="Hi!"),
                ]

                history = agent.get_session_history("test-session")

                assert len(history) == 2
                assert isinstance(history[0], HumanMessage)
                assert history[0].content == "Hello"
                assert isinstance(history[1], AIMessage)

    def test_clear_conversation(self, mock_settings):
        """Test clearing conversation history."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                agent._conversation_history["test-session"] = [
                    HumanMessage(content="Hello"),
                ]

                result = agent.clear_conversation("test-session")

                assert result is True
                assert "test-session" not in agent._conversation_history

    def test_clear_nonexistent_conversation(self, mock_settings):
        """Test clearing non-existent conversation."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent()

                result = agent.clear_conversation("non-existent")

                assert result is False


@pytest.mark.skip(reason="Quick methods (analyze_portfolio, assess_risk, check_compliance) not implemented")
class TestQuickMethods:
    """Tests for quick analysis methods."""

    @pytest.mark.asyncio
    async def test_analyze_portfolio(self, mock_settings):
        """Test analyze_portfolio quick method."""
        pass  # Method not implemented

    @pytest.mark.asyncio
    async def test_assess_risk(self, mock_settings):
        """Test assess_risk quick method."""
        pass  # Method not implemented

    @pytest.mark.asyncio
    async def test_check_compliance(self, mock_settings):
        """Test check_compliance quick method."""
        pass  # Method not implemented


class TestSingleton:
    """Tests for singleton agent instance."""

    def test_get_agent_singleton(self, mock_settings):
        """Test that get_agent returns a singleton."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                # Reset singleton
                import src.agent.core as core
                core._agent_instance = None

                agent1 = get_agent()
                agent2 = get_agent()

                assert agent1 is agent2


class TestPrompts:
    """Tests for agent prompts."""

    def test_system_prompt_exists(self):
        """Test that system prompt is defined."""
        assert SYSTEM_PROMPT is not None
        assert len(SYSTEM_PROMPT) > 100
        assert "portfolio" in SYSTEM_PROMPT.lower()
        assert "risk" in SYSTEM_PROMPT.lower()

    def test_tool_selection_prompt_exists(self):
        """Test that tool selection prompt is defined."""
        assert TOOL_SELECTION_PROMPT is not None
        assert "portfolio_analysis" in TOOL_SELECTION_PROMPT
        assert "risk_assessment" in TOOL_SELECTION_PROMPT

    def test_verification_prompt_exists(self):
        """Test that verification prompt is defined."""
        assert VERIFICATION_PROMPT is not None
        assert "accuracy" in VERIFICATION_PROMPT.lower()
        assert "confidence" in VERIFICATION_PROMPT.lower()


class TestVerificationIntegration:
    """Tests for verification integration."""

    @pytest.mark.asyncio
    async def test_verification_called_in_chat(self, mock_settings):
        """Test that verification is called during chat."""
        with patch("src.agent.core.get_settings", return_value=mock_settings):
            with patch("src.agent.core.ChatOpenAI"):
                agent = GhostfolioAgent(use_verification=True)

                mock_state = {
                    "messages": [AIMessage(content="Your portfolio is worth $100,000.")],
                    "current_tool_calls": [],
                    "_tool_outputs": [{"total_value": 100000}],
                    "errors": [],
                }

                agent.graph.ainvoke = AsyncMock(return_value=mock_state)

                # Mock verification
                from src.verification import EscalationStatus, VerificationReport
                mock_report = VerificationReport(
                    passed=True,
                    confidence_score=95.0,
                    confidence_level="VERY_HIGH",
                    escalation=EscalationStatus(),
                )
                agent.verification.verify = AsyncMock(return_value=mock_report)

                result = await agent.chat_with_context(
                    "What's my portfolio worth?",
                    session_id="test"
                )

                assert result["confidence"] == 95.0
                assert result["verification_passed"] is True
                agent.verification.verify.assert_called_once()
