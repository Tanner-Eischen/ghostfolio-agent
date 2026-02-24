"""Confidence scoring verification module.

Calculates confidence scores for agent responses based on:
1. Data completeness - how complete was the input data
2. Tool success rate - did all tools execute successfully
3. Response grounding - does response cite data sources
4. Numerical consistency - are numbers consistent with tool outputs
"""

import re
from typing import Any

from pydantic import BaseModel, Field

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ConfidenceAssessment(BaseModel):
    """Result of confidence assessment."""

    score: float = Field(ge=0, le=100, description="Overall confidence score 0-100")
    level: str = Field(description="Confidence level: LOW, MEDIUM, HIGH, VERY_HIGH")
    data_completeness: float = Field(ge=0, le=100, description="Data completeness score")
    tool_success_rate: float = Field(ge=0, le=100, description="Tool execution success rate")
    grounding_score: float = Field(ge=0, le=100, description="Response grounding score")
    concerns: list[str] = Field(default_factory=list, description="Identified concerns")
    recommendations: list[str] = Field(default_factory=list, description="Recommendations")


# Confidence thresholds
VERY_HIGH_THRESHOLD = 90
HIGH_THRESHOLD = 80
MEDIUM_THRESHOLD = 70
LOW_THRESHOLD = 50

# Escalation threshold (from PRE-SEARCH.md)
ESCALATION_THRESHOLD = 70


class ConfidenceScorer:
    """Calculate confidence scores for agent responses."""

    def __init__(self) -> None:
        """Initialize confidence scorer."""
        self.escalation_threshold = ESCALATION_THRESHOLD

    async def calculate_confidence(
        self,
        response: str,
        tool_outputs: list[dict[str, Any]],
        verification_results: dict[str, Any] | None = None,
    ) -> ConfidenceAssessment:
        """Calculate overall confidence score.

        The confidence score is a weighted combination of:
        - Data completeness (30%)
        - Tool success rate (25%)
        - Grounding score (25%)
        - Constraint violations (20% penalty per violation)

        Args:
            response: Agent response text
            tool_outputs: List of tool call outputs
            verification_results: Results from other verification checks

        Returns:
            ConfidenceAssessment with score and breakdown
        """
        # Calculate individual scores
        data_completeness = await self.assess_data_completeness(tool_outputs)
        tool_success_rate = self._calculate_tool_success_rate(tool_outputs)
        grounding_score = await self._assess_grounding(response, tool_outputs)

        # Calculate base score (weighted average)
        base_score = (
            data_completeness * 0.30 +
            tool_success_rate * 0.25 +
            grounding_score * 0.45
        )

        # Apply penalties from verification results
        concerns: list[str] = []
        recommendations: list[str] = []

        if verification_results:
            # Penalize constraint violations
            violations = verification_results.get("constraint_violations", [])
            if violations:
                base_score -= len(violations) * 10
                concerns.extend([f"Constraint violation: {v}" for v in violations])

            # Penalize fact check failures
            fact_failures = verification_results.get("fact_check_failures", [])
            if fact_failures:
                base_score -= len(fact_failures) * 15
                concerns.extend([f"Unverified claim: {f}" for f in fact_failures])

        # Ensure score is in valid range
        score = max(0, min(100, base_score))

        # Determine confidence level
        if score >= VERY_HIGH_THRESHOLD:
            level = "VERY_HIGH"
        elif score >= HIGH_THRESHOLD:
            level = "HIGH"
        elif score >= MEDIUM_THRESHOLD:
            level = "MEDIUM"
        elif score >= LOW_THRESHOLD:
            level = "LOW"
        else:
            level = "VERY_LOW"

        # Generate recommendations
        if data_completeness < 80:
            recommendations.append("Consider requesting additional data for complete analysis")
        if tool_success_rate < 100:
            recommendations.append("Some tools failed - review error messages")
        if grounding_score < 70:
            recommendations.append("Response should cite specific data sources")
        if score < self.escalation_threshold:
            recommendations.append("Confidence below threshold - consider human review")

        assessment = ConfidenceAssessment(
            score=round(score, 1),
            level=level,
            data_completeness=round(data_completeness, 1),
            tool_success_rate=round(tool_success_rate, 1),
            grounding_score=round(grounding_score, 1),
            concerns=concerns,
            recommendations=recommendations,
        )

        logger.info(
            f"Confidence assessment: {score:.1f}% ({level}) - "
            f"completeness={data_completeness:.1f}%, "
            f"tools={tool_success_rate:.1f}%, "
            f"grounding={grounding_score:.1f}%"
        )

        return assessment

    async def assess_data_completeness(
        self,
        tool_outputs: list[dict[str, Any]],
    ) -> float:
        """Assess how complete the data is.

        Checks for:
        - Empty tool outputs
        - Missing required fields
        - Null/None values
        - Partial data indicators

        Args:
            tool_outputs: List of tool call outputs

        Returns:
            Completeness score from 0-100
        """
        if not tool_outputs:
            return 0.0

        total_fields = 0
        complete_fields = 0

        for output in tool_outputs:
            # Check for error status
            if output.get("error") or output.get("status") == "error":
                # Error outputs are considered incomplete
                total_fields += 5
                continue

            # Recursively count fields
            fields_complete, fields_total = self._count_complete_fields(output)
            total_fields += fields_total
            complete_fields += fields_complete

        if total_fields == 0:
            return 100.0  # Empty but valid

        return (complete_fields / total_fields) * 100

    def _count_complete_fields(self, data: Any, depth: int = 0) -> tuple[int, int]:
        """Recursively count complete vs total fields.

        Args:
            data: Data structure to analyze
            depth: Current recursion depth (max 5)

        Returns:
            Tuple of (complete_fields, total_fields)
        """
        if depth > 5:  # Prevent infinite recursion
            return 1, 1

        if data is None:
            return 0, 1

        if isinstance(data, bool):
            return 1, 1  # Booleans are always complete

        if isinstance(data, (int, float, str)):
            # Empty strings are incomplete
            if isinstance(data, str) and not data.strip():
                return 0, 1
            return 1, 1

        if isinstance(data, list):
            if not data:
                return 0, 1  # Empty lists are incomplete
            complete, total = 0, 0
            for item in data:
                c, t = self._count_complete_fields(item, depth + 1)
                complete += c
                total += t
            return complete, total

        if isinstance(data, dict):
            if not data:
                return 0, 1  # Empty dicts are incomplete
            complete, total = 0, 0
            for key, value in data.items():
                # Skip metadata keys
                if key.startswith("_"):
                    continue
                c, t = self._count_complete_fields(value, depth + 1)
                complete += c
                total += t
            return complete, total

        return 1, 1  # Unknown types assumed complete

    def _calculate_tool_success_rate(self, tool_outputs: list[dict[str, Any]]) -> float:
        """Calculate percentage of tools that succeeded.

        Args:
            tool_outputs: List of tool call outputs

        Returns:
            Success rate from 0-100
        """
        if not tool_outputs:
            return 100.0  # No tools called is fine

        success_count = 0
        for output in tool_outputs:
            # Check for explicit error status
            if output.get("error"):
                continue
            if output.get("status") == "error":
                continue
            # Check for exception indicators
            if "exception" in str(output).lower():
                continue
            success_count += 1

        return (success_count / len(tool_outputs)) * 100

    async def _assess_grounding(
        self,
        response: str,
        tool_outputs: list[dict[str, Any]],
    ) -> float:
        """Assess how well the response is grounded in tool outputs.

        Checks for:
        - Numerical values in response matching tool outputs
        - Citations or references to data sources
        - Absence of made-up numbers

        Args:
            response: Agent response text
            tool_outputs: List of tool call outputs

        Returns:
            Grounding score from 0-100
        """
        if not tool_outputs:
            # No tools called - check if response acknowledges uncertainty
            uncertainty_phrases = [
                "i don't have", "no data", "cannot determine",
                "unable to", "not available", "unclear"
            ]
            response_lower = response.lower()
            if any(phrase in response_lower for phrase in uncertainty_phrases):
                return 80.0  # Good - acknowledges limitations
            return 50.0  # Medium - no tools but no acknowledgment

        # Extract numbers from response
        response_numbers = self._extract_numbers(response)

        # Extract numbers from tool outputs
        tool_numbers = set()
        self._extract_numbers_from_dict(tool_outputs, tool_numbers)

        # Check if response numbers appear in tool outputs
        grounded_numbers = 0
        ungrounded_numbers = 0

        for num in response_numbers:
            # Allow 1% tolerance for floating point
            is_grounded = any(
                abs(num - tool_num) < 0.01 * max(abs(num), 1)
                for tool_num in tool_numbers
            )
            if is_grounded:
                grounded_numbers += 1
            elif num > 100:  # Only flag larger numbers (not percentages)
                ungrounded_numbers += 1

        # Calculate grounding score
        total_significant_numbers = grounded_numbers + ungrounded_numbers
        if total_significant_numbers == 0:
            # No significant numbers in response
            # Score based on whether response references data
            if any(word in response.lower() for word in ["data", "portfolio", "position"]):
                return 75.0
            return 60.0

        grounding_ratio = grounded_numbers / total_significant_numbers

        # Bonus for citing sources
        source_indicators = ["according to", "based on", "data shows", "source:", "from"]
        has_citation = any(indicator in response.lower() for indicator in source_indicators)
        citation_bonus = 10 if has_citation else 0

        score = min(100, (grounding_ratio * 90) + citation_bonus)
        return score

    def _extract_numbers(self, text: str) -> list[float]:
        """Extract numerical values from text.

        Args:
            text: Text to extract numbers from

        Returns:
            List of numbers found
        """
        # Match numbers with optional decimals and commas
        pattern = r'\$?([\d,]+(?:\.\d+)?)\%?'
        matches = re.findall(pattern, text)

        numbers = []
        for match in matches:
            try:
                # Remove commas and convert to float
                num = float(match.replace(',', ''))
                numbers.append(num)
            except ValueError:
                continue

        return numbers

    def _extract_numbers_from_dict(
        self,
        data: Any,
        numbers: set[float],
        depth: int = 0,
    ) -> None:
        """Recursively extract numbers from a dictionary.

        Args:
            data: Data structure to extract from
            numbers: Set to add found numbers to
            depth: Current recursion depth
        """
        if depth > 5:
            return

        if isinstance(data, (int, float)) and not isinstance(data, bool):
            numbers.add(float(data))
        elif isinstance(data, dict):
            for value in data.values():
                self._extract_numbers_from_dict(value, numbers, depth + 1)
        elif isinstance(data, list):
            for item in data:
                self._extract_numbers_from_dict(item, numbers, depth + 1)

    def requires_escalation(self, confidence_score: float) -> bool:
        """Check if confidence score requires human escalation.

        Args:
            confidence_score: The confidence score to check

        Returns:
            True if escalation is required
        """
        return confidence_score < self.escalation_threshold

    async def llm_self_assessment(
        self,
        response: str,
        query: str,
    ) -> dict[str, Any]:
        """Use LLM to self-assess confidence (placeholder for future implementation).

        This method is designed to use an LLM to assess its own confidence
        in the response. For now, it returns a structured placeholder.

        Args:
            response: Agent response
            query: Original user query

        Returns:
            Self-assessment with confidence, reasoning, and concerns
        """
        # This is a placeholder implementation
        # In production, this would call the LLM with a self-assessment prompt
        return {
            "confidence": None,
            "reasoning": "LLM self-assessment not yet implemented",
            "concerns": [],
            "implementation_status": "placeholder",
        }


__all__ = [
    "ConfidenceScorer",
    "ConfidenceAssessment",
    "ESCALATION_THRESHOLD",
    "VERY_HIGH_THRESHOLD",
    "HIGH_THRESHOLD",
    "MEDIUM_THRESHOLD",
    "LOW_THRESHOLD",
]
