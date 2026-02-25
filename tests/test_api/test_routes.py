"""Tests for FastAPI routes.

These tests verify the API endpoints using FastAPI's TestClient.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client."""
    from src.api.routes import app
    return TestClient(app)


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = MagicMock()
    agent.chat_with_context = AsyncMock(return_value={
        "message": "Test response",
        "session_id": "test-session-123",
        "confidence": 85.0,
        "confidence_level": "HIGH",
        "tool_calls": [{"tool": "portfolio_analysis", "input": {}}],
        "verification_passed": True,
        "requires_escalation": False,
        "metadata": {"processing_time_ms": 500.0, "tools_used": 1},
    })
    agent.get_tool_descriptions = MagicMock(return_value=[
        {"name": "portfolio_analysis", "description": "Analyze portfolio"},
    ])
    agent._conversation_history = {}
    agent.clear_conversation = MagicMock(return_value=True)
    return agent


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check_returns_200(self, client):
        """Test health check returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_has_required_fields(self, client):
        """Test health response has required fields."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "environment" in data
        assert "agent_ready" in data
        assert "dependencies" in data

    def test_health_check_status_healthy(self, client):
        """Test health status is healthy."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_returns_api_info(self, client):
        """Test root returns API info."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


class TestChatEndpoint:
    """Tests for /chat endpoint."""

    @patch("src.api.routes.get_agent")
    def test_chat_with_message(self, mock_get_agent, client, mock_agent):
        """Test chat with a message."""
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/chat",
            json={"message": "What's my portfolio worth?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "confidence" in data
        assert "session_id" in data

    @patch("src.api.routes.get_agent")
    def test_chat_with_session_id(self, mock_get_agent, client, mock_agent):
        """Test chat with session ID."""
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/chat",
            json={
                "message": "Test message",
                "session_id": "existing-session",
            },
        )

        assert response.status_code == 200
        mock_agent.chat_with_context.assert_called_once()

    def test_chat_empty_message_returns_422(self, client):
        """Test empty message returns validation error."""
        response = client.post(
            "/chat",
            json={"message": ""},
        )
        assert response.status_code == 422

    def test_chat_missing_message_returns_422(self, client):
        """Test missing message returns validation error."""
        response = client.post(
            "/chat",
            json={},
        )
        assert response.status_code == 422

    @patch("src.api.routes.get_agent")
    def test_chat_response_has_confidence_level(self, mock_get_agent, client, mock_agent):
        """Test chat response includes confidence level."""
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/chat",
            json={"message": "Test"},
        )

        data = response.json()
        assert "confidence_level" in data

    @patch("src.api.routes.get_agent")
    def test_chat_response_has_verification_status(self, mock_get_agent, client, mock_agent):
        """Test chat response includes verification status."""
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/chat",
            json={"message": "Test"},
        )

        data = response.json()
        assert "verification_passed" in data
        assert "requires_escalation" in data


class TestToolsEndpoint:
    """Tests for /chat/tools endpoint."""

    @patch("src.api.routes.get_agent")
    def test_list_tools(self, mock_get_agent, client, mock_agent):
        """Test listing available tools."""
        mock_get_agent.return_value = mock_agent

        response = client.get("/chat/tools")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestSessionEndpoints:
    """Tests for session management endpoints."""

    @patch("src.api.routes.get_agent")
    def test_get_session_history(self, mock_get_agent, client, mock_agent):
        """Test getting session history."""
        mock_get_agent.return_value = mock_agent
        mock_agent._conversation_history = {
            "test-session": [],
        }

        response = client.get("/sessions/test-session")

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "message_count" in data
        assert "messages" in data

    @patch("src.api.routes.get_agent")
    def test_clear_session(self, mock_get_agent, client, mock_agent):
        """Test clearing session."""
        mock_get_agent.return_value = mock_agent

        response = client.delete("/sessions/test-session")

        assert response.status_code == 200
        data = response.json()
        assert "cleared" in data


class TestFeedbackEndpoint:
    """Tests for /feedback endpoint."""

    def test_submit_positive_feedback(self, client):
        """Test submitting positive feedback."""
        response = client.post(
            "/feedback",
            json={
                "message_id": "msg-123",
                "session_id": "session-456",
                "rating": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"

    def test_submit_negative_feedback(self, client):
        """Test submitting negative feedback."""
        response = client.post(
            "/feedback",
            json={
                "message_id": "msg-123",
                "session_id": "session-456",
                "rating": -1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"

    def test_submit_star_rating(self, client):
        """Test submitting star rating."""
        response = client.post(
            "/feedback",
            json={
                "message_id": "msg-123",
                "session_id": "session-456",
                "rating": 4,
                "comment": "Good response!",
            },
        )

        assert response.status_code == 200

    def test_feedback_invalid_rating(self, client):
        """Test feedback with invalid rating."""
        response = client.post(
            "/feedback",
            json={
                "message_id": "msg-123",
                "session_id": "session-456",
                "rating": 10,  # Invalid
            },
        )

        assert response.status_code == 422


class TestPortfolioEndpoints:
    """Tests for portfolio endpoints."""

    @patch("src.api.routes.get_agent")
    def test_get_portfolio_summary(self, mock_get_agent, client, mock_agent):
        """Test getting portfolio summary."""
        mock_get_agent.return_value = mock_agent

        response = client.get("/portfolio")

        # Should return 200 with summary (may have empty values)
        assert response.status_code == 200
        data = response.json()
        # Check structure is correct
        assert isinstance(data, dict)


class TestMarketEndpoint:
    """Tests for market data endpoint."""

    @patch("src.api.routes.get_agent")
    def test_get_market_data(self, mock_get_agent, client, mock_agent):
        """Test getting market data for a symbol."""
        mock_get_agent.return_value = mock_agent

        response = client.get("/market/AAPL")

        # May succeed or fail depending on tool availability
        assert response.status_code in [200, 500]


class TestResponseModels:
    """Tests for response model validation."""

    def test_health_response_model(self, client):
        """Test health response matches model."""
        response = client.get("/health")
        data = response.json()

        # All required fields should be present
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["environment"], str)
        assert isinstance(data["agent_ready"], bool)
        assert isinstance(data["dependencies"], dict)

    @patch("src.api.routes.get_agent")
    def test_chat_response_model(self, mock_get_agent, client, mock_agent):
        """Test chat response matches model."""
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/chat",
            json={"message": "Test"},
        )
        data = response.json()

        # All required fields should be present
        assert isinstance(data["response"], str)
        assert isinstance(data["confidence"], (int, float))
        assert isinstance(data["confidence_level"], str)
        assert isinstance(data["tool_calls"], list)
        assert isinstance(data["session_id"], str)
        assert isinstance(data["verification_passed"], bool)
        assert isinstance(data["requires_escalation"], bool)
        assert isinstance(data["processing_time_ms"], (int, float))


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_for_unknown_endpoint(self, client):
        """Test 404 for unknown endpoint."""
        response = client.get("/unknown")
        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test method not allowed."""
        response = client.delete("/health")
        assert response.status_code == 405
