"""Smoke tests for core endpoints - run without external dependencies."""

import os

# Force mock mode for all smoke tests
os.environ["USE_MOCK_DATA"] = "true"
os.environ["OPENAI_API_KEY"] = "test-key"

import pytest
from fastapi.testclient import TestClient


from src.api.app import app


@pytest.fixture(scope="module")
def client():
    """Create test client with mock data enabled."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test /health returns valid response."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "ok"]
    assert "version" in data


def test_root_endpoint(client):
    """Test root returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    assert "name" in response.json()


def test_tools_endpoint(client):
    """Test /chat/tools returns tool list."""
    response = client.get("/chat/tools")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_feedback_endpoint(client):
    """Test /feedback accepts rating."""
    response = client.post("/feedback", json={
        "message_id": "test",
        "session_id": "test",
        "rating": 1
    })
    assert response.status_code == 200
    assert response.json()["status"] == "received"


def test_sessions_list(client):
    """Test /sessions returns session list."""
    response = client.get("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data


def test_portfolio_endpoint(client):
    """Test /portfolio returns portfolio summary in mock mode."""
    response = client.get("/portfolio")
    # May return 400 if no token is set, or 200 with mock data
    assert response.status_code in [200, 400]
