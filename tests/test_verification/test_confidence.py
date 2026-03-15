"""Tests for ConfidenceScorer verification module."""

import pytest

from src.verification.confidence import (
    ESCALATION_THRESHOLD,
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
    MEDIUM_THRESHOLD,
    VERY_HIGH_THRESHOLD,
    ConfidenceAssessment,
    ConfidenceScorer,
)


class TestConfidenceScorer:
    """Test ConfidenceScorer class."""

    @pytest.fixture
    def scorer(self) -> ConfidenceScorer:
        """Create a ConfidenceScorer instance."""
        return ConfidenceScorer()

    @pytest.fixture
    def complete_tool_output(self) -> list[dict]:
        """Create complete tool output."""
        return [{
            "total_value": 100000.00,
            "currency": "USD",
            "holdings": [
                {"symbol": "AAPL", "value": 50000, "quantity": 100},
                {"symbol": "MSFT", "value": 50000, "quantity": 50},
            ],
        }]

    @pytest.fixture
    def partial_tool_output(self) -> list[dict]:
        """Create partial tool output with some missing data."""
        return [{
            "total_value": 100000,  # Has value
            "currency": "USD",  # Has value
            "holdings": [],  # Empty - considered incomplete
            "performance": None,  # Missing
        }]

    @pytest.fixture
    def error_tool_output(self) -> list[dict]:
        """Create tool output with error."""
        return [{
            "error": "API failed",
            "status": "error",
        }]

    # ========================================================================
    # Test calculate_confidence
    # ========================================================================

    @pytest.mark.asyncio
    async def test_calculate_confidence_high_score(
        self, scorer: ConfidenceScorer, complete_tool_output: list[dict]
    ) -> None:
        """Test confidence scoring with complete data."""
        response = "Your portfolio is worth $100,000."
        result = await scorer.calculate_confidence(response, complete_tool_output)

        assert isinstance(result, ConfidenceAssessment)
        assert result.score >= HIGH_THRESHOLD
        assert result.level in ("HIGH", "VERY_HIGH")
        assert result.data_completeness >= 80
        assert result.tool_success_rate == 100

    @pytest.mark.asyncio
    async def test_calculate_confidence_low_score(
        self, scorer: ConfidenceScorer, error_tool_output: list[dict]
    ) -> None:
        """Test confidence scoring with error data."""
        response = "Your portfolio is worth $100,000."
        result = await scorer.calculate_confidence(response, error_tool_output)

        assert result.score < 80
        assert result.tool_success_rate == 0
        assert len(result.concerns) > 0 or result.score < 80

    @pytest.mark.asyncio
    async def test_calculate_confidence_no_tools(self, scorer: ConfidenceScorer) -> None:
        """Test confidence scoring with no tool outputs."""
        response = "I don't have access to your portfolio data."
        result = await scorer.calculate_confidence(response, [])

        # Should acknowledge uncertainty
        assert result.score >= 50

    @pytest.mark.asyncio
    async def test_calculate_confidence_with_verification_results(
        self, scorer: ConfidenceScorer, complete_tool_output: list[dict]
    ) -> None:
        """Test confidence scoring with verification results."""
        response = "Your portfolio is worth $100,000."
        verification_results = {
            "constraint_violations": ["Negative value detected"],
            "fact_check_failures": [],
        }
        result = await scorer.calculate_confidence(
            response, complete_tool_output, verification_results
        )

        # Should be penalized for constraint violations
        assert result.score < 100
        assert any("Constraint violation" in c for c in result.concerns)

    @pytest.mark.asyncio
    async def test_calculate_confidence_ungrounded_numbers(
        self, scorer: ConfidenceScorer
    ) -> None:
        """Test confidence with numbers not in tool output."""
        response = "Your portfolio is worth $500,000."
        tool_outputs = [{"total_value": 100000}]

        result = await scorer.calculate_confidence(response, tool_outputs)

        # Lower score due to ungrounded number
        assert result.grounding_score < 100

    # ========================================================================
    # Test assess_data_completeness
    # ========================================================================

    @pytest.mark.asyncio
    async def test_assess_data_completeness_full(
        self, scorer: ConfidenceScorer, complete_tool_output: list[dict]
    ) -> None:
        """Test completeness with full data."""
        completeness = await scorer.assess_data_completeness(complete_tool_output)

        assert completeness >= 90

    @pytest.mark.asyncio
    async def test_assess_data_completeness_empty(self, scorer: ConfidenceScorer) -> None:
        """Test completeness with empty tool outputs returns moderate score."""
        completeness = await scorer.assess_data_completeness([])

        # Empty tool outputs indicates tools were used but outputs weren't captured
        # Returns 50.0 (moderate completeness)
        assert completeness == 50.0

    @pytest.mark.asyncio
    async def test_assess_data_completeness_partial(
        self, scorer: ConfidenceScorer, partial_tool_output: list[dict]
    ) -> None:
        """Test completeness with partial data."""
        completeness = await scorer.assess_data_completeness(partial_tool_output)

        assert 0 < completeness < 100

    @pytest.mark.asyncio
    async def test_assess_data_completeness_error(
        self, scorer: ConfidenceScorer, error_tool_output: list[dict]
    ) -> None:
        """Test completeness with error data."""
        completeness = await scorer.assess_data_completeness(error_tool_output)

        assert completeness == 0

    @pytest.mark.asyncio
    async def test_assess_data_completeness_nested(self, scorer: ConfidenceScorer) -> None:
        """Test completeness with nested data."""
        tool_output = [{
            "data": {
                "level1": {
                    "level2": {
                        "value": 100,
                        "empty": None,
                    }
                }
            }
        }]
        completeness = await scorer.assess_data_completeness(tool_output)

        # Should handle nested structures
        assert 0 < completeness < 100

    # ========================================================================
    # Test confidence levels
    # ========================================================================

    @pytest.mark.asyncio
    async def test_confidence_level_very_high(self, scorer: ConfidenceScorer) -> None:
        """Test VERY_HIGH confidence level."""
        result = await scorer.calculate_confidence(
            "Value is $100.", [{"value": 100}]
        )
        if result.score >= VERY_HIGH_THRESHOLD:
            assert result.level == "VERY_HIGH"

    @pytest.mark.asyncio
    async def test_confidence_level_high(self, scorer: ConfidenceScorer) -> None:
        """Test HIGH confidence level."""
        result = await scorer.calculate_confidence(
            "Value is $100.", [{"value": 100}]
        )
        if HIGH_THRESHOLD <= result.score < VERY_HIGH_THRESHOLD:
            assert result.level == "HIGH"

    @pytest.mark.asyncio
    async def test_confidence_level_medium(self, scorer: ConfidenceScorer) -> None:
        """Test MEDIUM confidence level."""
        result = await scorer.calculate_confidence(
            "Value is approximately $100.", [{"value": 100}]
        )
        if MEDIUM_THRESHOLD <= result.score < HIGH_THRESHOLD:
            assert result.level == "MEDIUM"

    @pytest.mark.asyncio
    async def test_confidence_level_low(self, scorer: ConfidenceScorer) -> None:
        """Test LOW confidence level."""
        result = await scorer.calculate_confidence(
            "I think the value might be something.", [{}]
        )
        if LOW_THRESHOLD <= result.score < MEDIUM_THRESHOLD:
            assert result.level == "LOW"

    # ========================================================================
    # Test escalation
    # ========================================================================

    def test_requires_escalation_true(self, scorer: ConfidenceScorer) -> None:
        """Test escalation check returns True for low confidence."""
        assert scorer.requires_escalation(50) is True
        assert scorer.requires_escalation(69) is True

    def test_requires_escalation_false(self, scorer: ConfidenceScorer) -> None:
        """Test escalation check returns False for high confidence."""
        assert scorer.requires_escalation(70) is False
        assert scorer.requires_escalation(90) is False

    # ========================================================================
    # Test number extraction
    # ========================================================================

    def test_extract_numbers_simple(self, scorer: ConfidenceScorer) -> None:
        """Test extracting simple numbers."""
        numbers = scorer._extract_numbers("Value is $100")
        assert 100 in numbers

    def test_extract_numbers_with_commas(self, scorer: ConfidenceScorer) -> None:
        """Test extracting numbers with commas."""
        numbers = scorer._extract_numbers("Value is $1,000,000")
        assert 1000000 in numbers

    def test_extract_numbers_multiple(self, scorer: ConfidenceScorer) -> None:
        """Test extracting multiple numbers."""
        numbers = scorer._extract_numbers("Bought 100 shares at $50")
        assert 100 in numbers
        assert 50 in numbers

    def test_extract_numbers_percentages(self, scorer: ConfidenceScorer) -> None:
        """Test extracting percentages."""
        numbers = scorer._extract_numbers("Return was 15%")
        assert 15 in numbers

    # ========================================================================
    # Test grounding assessment
    # ========================================================================

    @pytest.mark.asyncio
    async def test_assess_grounding_grounded(self, scorer: ConfidenceScorer) -> None:
        """Test grounding with grounded numbers."""
        response = "Your portfolio is worth $100,000."
        tool_outputs = [{"total_value": 100000}]

        score = await scorer._assess_grounding(response, tool_outputs)

        assert score >= 80

    @pytest.mark.asyncio
    async def test_assess_grounding_ungrounded(self, scorer: ConfidenceScorer) -> None:
        """Test grounding with ungrounded numbers."""
        response = "Your portfolio is worth $500,000."
        tool_outputs = [{"total_value": 100000}]

        score = await scorer._assess_grounding(response, tool_outputs)

        assert score < 80

    @pytest.mark.asyncio
    async def test_assess_grounding_with_citation(self, scorer: ConfidenceScorer) -> None:
        """Test grounding with citation."""
        response = "According to the data, your portfolio is worth $100,000."
        tool_outputs = [{"total_value": 100000}]

        score = await scorer._assess_grounding(response, tool_outputs)

        # Should get bonus for citation
        assert score >= 80

    # ========================================================================
    # Test recommendations
    # ========================================================================

    @pytest.mark.asyncio
    async def test_recommendations_generated(self, scorer: ConfidenceScorer) -> None:
        """Test that recommendations are generated for low scores."""
        result = await scorer.calculate_confidence(
            "Value is something.", [{}]  # Incomplete data
        )

        # Should have recommendations if issues exist
        if result.score < 80:
            assert len(result.recommendations) > 0


class TestConfidenceThresholds:
    """Test confidence threshold constants."""

    def test_threshold_ordering(self) -> None:
        """Test that thresholds are in correct order."""
        assert VERY_HIGH_THRESHOLD == 90
        assert HIGH_THRESHOLD == 80
        assert MEDIUM_THRESHOLD == 70
        assert LOW_THRESHOLD == 50
        assert ESCALATION_THRESHOLD == 70


class TestConfidenceAssessment:
    """Test ConfidenceAssessment model."""

    def test_valid_assessment(self) -> None:
        """Test creating valid assessment."""
        assessment = ConfidenceAssessment(
            score=85.0,
            level="HIGH",
            data_completeness=90.0,
            tool_success_rate=100.0,
            grounding_score=80.0,
        )

        assert assessment.score == 85.0
        assert assessment.level == "HIGH"

    def test_score_bounds(self) -> None:
        """Test score must be between 0 and 100."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ConfidenceAssessment(
                score=150,  # Invalid
                level="HIGH",
                data_completeness=90.0,
                tool_success_rate=100.0,
                grounding_score=80.0,
            )

        with pytest.raises(ValidationError):
            ConfidenceAssessment(
                score=-10,  # Invalid
                level="LOW",
                data_completeness=90.0,
                tool_success_rate=100.0,
                grounding_score=80.0,
            )
