"""E2E tests for /chat: real agent and LLM (no mocks).

Run with OPENAI_API_KEY set. Skip if not set.
  pytest tests/test_api/test_chat_e2e.py -v
  pytest tests/test_api/test_chat_e2e.py -v -k "greeting"
"""

import os
import pytest
from fastapi.testclient import TestClient


def _openai_available():
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


@pytest.fixture(scope="module")
def client():
    from src.api.routes import app
    return TestClient(app)


@pytest.mark.skipif(not _openai_available(), reason="OPENAI_API_KEY not set")
class TestChatE2E:
    """E2E chat tests against real agent and LLM."""

    def test_chat_greeting_returns_200_conversational(self, client):
        """Greeting like 'hey' gets 200 and a conversational reply, not access-token message."""
        response = client.post(
            "/chat",
            json={"message": "hey"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "response" in data
        text = data["response"].lower()
        # Greeting should get a conversational reply, not the Ghostfolio setup/error message
        assert "can't access your portfolio" not in text
        assert "access token" not in text
        assert "session_id" in data
        assert len(data["response"].strip()) > 0

    def test_chat_greeting_hi_returns_200(self, client):
        """'Hi' gets 200 and non-empty response."""
        response = client.post(
            "/chat",
            json={"message": "Hi"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["response"], str)
        assert len(data["response"].strip()) > 0

    def test_chat_portfolio_query_returns_200(self, client):
        """Portfolio query returns 200 (may be data or friendly error if no Ghostfolio)."""
        response = client.post(
            "/chat",
            json={"message": "What's my portfolio value?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert "confidence" in data
        assert "tool_calls" in data

    def test_chat_domain_question_returns_200(self, client):
        """Domain question (no tool needed) returns 200 and non-empty answer."""
        response = client.post(
            "/chat",
            json={"message": "What is diversification?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["response"].strip()) > 0
