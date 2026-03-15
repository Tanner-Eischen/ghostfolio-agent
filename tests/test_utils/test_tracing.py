"""Tests for LangSmith tracing utilities."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.utils.tracing import (
    TraceContext,
    configure_langsmith,
    get_langsmith_client,
    get_trace_url,
    log_feedback,
    traced,
)


@pytest.fixture
def mock_settings():
    """Create mock settings with LangSmith configured."""
    from src.utils.config import Settings
    return Settings(
        environment="development",
        openai_api_key="test_openai_key",
        langsmith_tracing=True,
        langsmith_api_key="lsv2_test_key_123",
        langsmith_endpoint="https://api.smith.langchain.com",
        langsmith_project="AgentForge",
        langsmith_workspace_id="test-workspace-id",
    )


class TestConfigureLangSmith:
    """Tests for LangSmith configuration."""

    def test_configure_with_api_key(self, mock_settings):
        """Test configuration when API key is present."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            # Clear environment
            os.environ.pop("LANGSMITH_API_KEY", None)

            result = configure_langsmith()

            assert result is True
            assert os.environ.get("LANGSMITH_API_KEY") == "lsv2_test_key_123"
            assert os.environ.get("LANGSMITH_TRACING") == "true"
            assert os.environ.get("LANGSMITH_PROJECT") == "AgentForge"

    def test_configure_without_api_key(self):
        """Test configuration when API key is missing."""
        from src.utils.config import Settings

        mock_settings = Settings(
            environment="development",
            openai_api_key="test",
            langsmith_api_key="",  # No API key
        )

        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            result = configure_langsmith()

            assert result is False


class TestGetLangSmithClient:
    """Tests for getting LangSmith client."""

    def test_client_with_api_key(self, mock_settings):
        """Test getting client when API key is present."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            with patch("src.utils.tracing.Client") as MockClient:
                client = get_langsmith_client()

                MockClient.assert_called_once()

    def test_client_without_api_key(self):
        """Test getting client when API key is missing."""
        from src.utils.config import Settings

        mock_settings = Settings(
            environment="development",
            openai_api_key="test",
            langsmith_api_key="",
        )

        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            client = get_langsmith_client()

            assert client is None


class TestGetTraceUrl:
    """Tests for trace URL generation."""

    def test_url_with_run_id(self, mock_settings):
        """Test URL generation with run ID."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            url = get_trace_url("run-123")

            assert url is not None
            assert "smith.langchain.com" in url
            assert "run-123" in url

    def test_url_without_run_id(self, mock_settings):
        """Test URL generation without run ID."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            url = get_trace_url()

            assert url is None

    def test_url_without_api_key(self):
        """Test URL generation without API key."""
        from src.utils.config import Settings

        mock_settings = Settings(
            environment="development",
            openai_api_key="test",
            langsmith_api_key="",
        )

        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            url = get_trace_url("run-123")

            assert url is None


class TestTracedDecorator:
    """Tests for the traced decorator."""

    @pytest.mark.asyncio
    async def test_traced_async_function(self, mock_settings):
        """Test tracing an async function."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            with patch("src.utils.tracing.traceable") as mock_traceable:
                # Setup traceable to just call the function
                mock_traceable.return_value = lambda f: f

                @traced("test_function")
                async def test_func():
                    return "result"

                result = await test_func()

                assert result == "result"

    def test_traced_sync_function(self, mock_settings):
        """Test tracing a sync function."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            with patch("src.utils.tracing.traceable") as mock_traceable:
                mock_traceable.return_value = lambda f: f

                @traced("test_function")
                def test_func():
                    return "result"

                result = test_func()

                assert result == "result"


class TestTraceContext:
    """Tests for TraceContext."""

    @pytest.mark.asyncio
    async def test_trace_context_with_api_key(self, mock_settings):
        """Test TraceContext with API key configured."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            with patch("src.utils.tracing.traceable") as mock_traceable:
                # traceable(**kwargs) should return a decorator that wraps the function
                mock_traceable.side_effect = lambda **kwargs: lambda f: f

                async with TraceContext("test_context") as ctx:
                    ctx.add_tags(["test"])
                    ctx.add_metadata({"key": "value"})

                assert "test" in ctx.tags
                assert ctx.metadata.get("key") == "value"

    @pytest.mark.asyncio
    async def test_trace_context_without_api_key(self):
        """Test TraceContext without API key."""
        from src.utils.config import Settings

        mock_settings = Settings(
            environment="development",
            openai_api_key="test",
            langsmith_api_key="",
        )

        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            async with TraceContext("test_context") as ctx:
                # Should not error, just not trace
                pass

    def test_add_tags(self, mock_settings):
        """Test adding tags to context."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            ctx = TraceContext("test")
            ctx.add_tags(["tag1", "tag2"])

            assert "tag1" in ctx.tags
            assert "tag2" in ctx.tags

    def test_add_metadata(self, mock_settings):
        """Test adding metadata to context."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            ctx = TraceContext("test")
            ctx.add_metadata({"key1": "value1"})

            assert ctx.metadata.get("key1") == "value1"


class TestLogFeedback:
    """Tests for logging feedback."""

    def test_log_feedback_with_client(self, mock_settings):
        """Test logging feedback with client configured."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            mock_client = MagicMock()
            with patch("src.utils.tracing.get_langsmith_client", return_value=mock_client):
                result = log_feedback("run-123", 0.9, key="rating", comment="Great!")

                assert result is True
                mock_client.create_feedback.assert_called_once()

    def test_log_feedback_without_client(self):
        """Test logging feedback without client."""
        from src.utils.config import Settings

        mock_settings = Settings(
            environment="development",
            openai_api_key="test",
            langsmith_api_key="",
        )

        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            result = log_feedback("run-123", 0.9)

            assert result is False

    def test_log_feedback_with_error(self, mock_settings):
        """Test logging feedback when client errors."""
        with patch("src.utils.tracing.get_settings", return_value=mock_settings):
            mock_client = MagicMock()
            mock_client.create_feedback.side_effect = Exception("API Error")

            with patch("src.utils.tracing.get_langsmith_client", return_value=mock_client):
                result = log_feedback("run-123", 0.9)

                assert result is False
