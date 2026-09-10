"""Tests for Streamlit frontend components.

These tests verify the helper functions and logic without
requiring a full Streamlit context.
"""

from unittest.mock import patch


class TestConfidenceStyles:
    """Tests for confidence score styling."""

    def test_very_high_confidence(self):
        """Test style for very high confidence (>=90)."""
        from app.streamlit_app import get_confidence_style

        style = get_confidence_style(95)
        assert style["color"] == "#28a745"
        assert style["emoji"] == "excellent"

    def test_high_confidence(self):
        """Test style for high confidence (80-89)."""
        from app.streamlit_app import get_confidence_style

        style = get_confidence_style(85)
        assert style["color"] == "#5cb85c"
        assert style["emoji"] == "good"

    def test_medium_confidence(self):
        """Test style for medium confidence (70-79)."""
        from app.streamlit_app import get_confidence_style

        style = get_confidence_style(75)
        assert style["color"] == "#ffc107"
        assert style["emoji"] == "moderate"

    def test_low_confidence(self):
        """Test style for low confidence (50-69)."""
        from app.streamlit_app import get_confidence_style

        style = get_confidence_style(60)
        assert style["color"] == "#fd7e14"
        assert style["emoji"] == "low"

    def test_very_low_confidence(self):
        """Test style for very low confidence (<50)."""
        from app.streamlit_app import get_confidence_style

        style = get_confidence_style(30)
        assert style["color"] == "#dc3545"
        assert style["emoji"] == "very-low"

    def test_boundary_very_high(self):
        """Test boundary case at 90."""
        from app.streamlit_app import get_confidence_style

        style = get_confidence_style(90)
        assert style["color"] == "#28a745"

    def test_boundary_high(self):
        """Test boundary case at 80."""
        from app.streamlit_app import get_confidence_style

        style = get_confidence_style(80)
        assert style["color"] == "#5cb85c"

    def test_boundary_medium(self):
        """Test boundary case at 70."""
        from app.streamlit_app import get_confidence_style

        style = get_confidence_style(70)
        assert style["color"] == "#ffc107"

    def test_boundary_low(self):
        """Test boundary case at 50."""
        from app.streamlit_app import get_confidence_style

        style = get_confidence_style(50)
        assert style["color"] == "#fd7e14"

    def test_zero_confidence(self):
        """Test zero confidence."""
        from app.streamlit_app import get_confidence_style

        style = get_confidence_style(0)
        assert style["color"] == "#dc3545"


class TestSendChatMessage:
    """Tests for the Streamlit backend client."""

    def test_connection_error_returns_dict(self):
        """Connection failures return the response shape used by the UI."""
        import httpx

        from app.streamlit_app import send_chat_message

        with patch("app.streamlit_app.httpx.Client", side_effect=httpx.ConnectError("offline")):
            result = send_chat_message("test", "session")
        assert isinstance(result, dict)
        assert "message" in result
        assert "confidence" in result
        assert result["confidence"] == 0.0

    def test_connection_error_requires_escalation(self):
        """Connection failures are marked for escalation."""
        import httpx

        from app.streamlit_app import send_chat_message

        with patch("app.streamlit_app.httpx.Client", side_effect=httpx.ConnectError("offline")):
            result = send_chat_message("test message", "test-session")

        assert result["verification_passed"] is False
        assert result["requires_escalation"] is True
        assert len(result["escalation_triggers"]) > 0


class TestPortfolioDataExtraction:
    """Tests for portfolio data extraction from messages."""

    def test_extract_portfolio_value_with_dollar_sign(self):
        """Test extracting portfolio value with $ sign."""
        from app.streamlit_app import try_extract_portfolio_data
        import streamlit as st

        # This is a stateful function, so we just verify it doesn't crash
        message = "Your portfolio is worth $125,000.00"
        try_extract_portfolio_data(message, "What's my portfolio worth?")

    def test_extract_portfolio_value_large(self):
        """Test extracting large portfolio value."""
        from app.streamlit_app import try_extract_portfolio_data

        message = "Your total portfolio value is $1,234,567.89"
        try_extract_portfolio_data(message, "test")

    def test_extract_performance_positive(self):
        """Test extracting positive performance."""
        from app.streamlit_app import try_extract_portfolio_data

        message = "Your portfolio is up 12.5% this year"
        try_extract_portfolio_data(message, "test")

    def test_extract_performance_negative(self):
        """Test extracting negative performance."""
        from app.streamlit_app import try_extract_portfolio_data

        message = "Your portfolio is down 5.3% this month"
        try_extract_portfolio_data(message, "test")


class TestConfidenceThresholds:
    """Tests for confidence threshold constants."""

    def test_thresholds_defined(self):
        """Test that all confidence thresholds are defined."""
        from app.streamlit_app import CONFIDENCE_THRESHOLDS

        assert "VERY_HIGH" in CONFIDENCE_THRESHOLDS
        assert "HIGH" in CONFIDENCE_THRESHOLDS
        assert "MEDIUM" in CONFIDENCE_THRESHOLDS
        assert "LOW" in CONFIDENCE_THRESHOLDS
        assert "VERY_LOW" in CONFIDENCE_THRESHOLDS

    def test_threshold_colors_are_hex(self):
        """Test that all threshold colors are valid hex."""
        from app.streamlit_app import CONFIDENCE_THRESHOLDS

        for level, config in CONFIDENCE_THRESHOLDS.items():
            color = config["color"]
            assert color.startswith("#")
            assert len(color) == 7

    def test_threshold_ordering(self):
        """Test that thresholds are in descending order."""
        from app.streamlit_app import CONFIDENCE_THRESHOLDS

        mins = [CONFIDENCE_THRESHOLDS[k]["min"] for k in
                ["VERY_HIGH", "HIGH", "MEDIUM", "LOW", "VERY_LOW"]]
        assert mins == sorted(mins, reverse=True)
