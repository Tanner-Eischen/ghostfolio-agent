"""Fact checking verification module.

Cross-references agent claims against:
1. Tool outputs - verifies claims match actual tool data
2. Numerical accuracy - checks numbers within tolerance
3. Source attribution - ensures claims cite data sources
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.utils.logging import get_logger

logger = get_logger(__name__)


class FactCheckResult(BaseModel):
    """Result of a single fact check."""

    claim: str = Field(description="The claim that was checked")
    is_accurate: bool = Field(description="Whether the claim is accurate")
    confidence: float = Field(ge=0, le=100, description="Confidence in the check")
    explanation: str = Field(description="Explanation of the result")
    source_value: Any | None = Field(default=None, description="The actual source value")
    claimed_value: Any | None = Field(default=None, description="The claimed value")


class CitationCheckResult(BaseModel):
    """Result of citation verification."""

    has_citations: bool = Field(description="Whether response contains citations")
    citation_count: int = Field(description="Number of citations found")
    verified_citations: int = Field(description="Number of citations verified against data")
    unverified_claims: list[str] = Field(default_factory=list, description="Claims without citation")
    accuracy_score: float = Field(ge=0, le=100, description="Overall accuracy score")


class FactChecker:
    """Cross-reference claims against data sources."""

    # Patterns for extracting claims
    NUMBER_PATTERN = r'\$?([\d,]+(?:\.\d+)?)\%?'
    DATE_PATTERN = r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}'

    # Keywords that indicate factual claims
    CLAIM_KEYWORDS = [
        "is", "are", "was", "were", "has", "have", "total", "value",
        "price", "worth", "performance", "return", "change", "gain", "loss",
        "allocation", "percentage", "ratio", "score", "rank"
    ]

    def __init__(self, numerical_tolerance: float = 0.01) -> None:
        """Initialize fact checker.

        Args:
            numerical_tolerance: Acceptable deviation for numerical claims (default 1%)
        """
        self.numerical_tolerance = numerical_tolerance

    async def verify_claim(
        self,
        claim: str,
        source_data: dict[str, Any],
    ) -> FactCheckResult:
        """Verify a claim against source data.

        Args:
            claim: The claim to verify
            source_data: Data to verify against

        Returns:
            FactCheckResult with verification details
        """
        # Extract numbers from the claim
        claimed_numbers = self._extract_numbers(claim)

        if not claimed_numbers:
            # No numerical claims to verify
            return FactCheckResult(
                claim=claim,
                is_accurate=True,
                confidence=50.0,
                explanation="No numerical values to verify",
                source_value=None,
                claimed_value=None,
            )

        # Extract all numbers from source data
        source_numbers = set()
        self._extract_numbers_from_data(source_data, source_numbers)

        # Check each claimed number
        inaccurate_numbers = []
        accurate_numbers = []

        for num in claimed_numbers:
            is_found = self._is_number_in_source(num, source_numbers)
            if is_found:
                accurate_numbers.append(num)
            else:
                inaccurate_numbers.append(num)

        # Determine overall accuracy
        if not inaccurate_numbers:
            return FactCheckResult(
                claim=claim,
                is_accurate=True,
                confidence=95.0,
                explanation=f"All {len(accurate_numbers)} numerical values verified",
                source_value=list(source_numbers)[:5] if source_numbers else None,
                claimed_value=claimed_numbers,
            )

        # Some numbers not found
        accuracy_ratio = len(accurate_numbers) / len(claimed_numbers)
        confidence = accuracy_ratio * 100

        return FactCheckResult(
            claim=claim,
            is_accurate=accuracy_ratio >= 0.8,  # 80% accuracy threshold
            confidence=confidence,
            explanation=f"{len(accurate_numbers)}/{len(claimed_numbers)} values verified. "
                       f"Unverified: {inaccurate_numbers}",
            source_value=list(source_numbers)[:5] if source_numbers else None,
            claimed_value=claimed_numbers,
        )

    async def verify_numerical_claim(
        self,
        claimed_value: float,
        actual_value: float,
        tolerance: float | None = None,
    ) -> bool:
        """Verify a numerical claim within tolerance.

        Args:
            claimed_value: The claimed number
            actual_value: The actual value
            tolerance: Acceptable deviation (default uses instance tolerance)

        Returns:
            Whether the claim is accurate within tolerance
        """
        if tolerance is None:
            tolerance = self.numerical_tolerance

        if actual_value == 0:
            return claimed_value == 0

        # Calculate percentage difference
        diff_pct = abs(claimed_value - actual_value) / abs(actual_value)

        is_accurate = diff_pct <= tolerance

        logger.debug(
            f"Numerical verification: claimed={claimed_value}, "
            f"actual={actual_value}, diff_pct={diff_pct:.2%}, "
            f"tolerance={tolerance:.2%}, accurate={is_accurate}"
        )

        return is_accurate

    async def extract_and_verify_citations(
        self,
        response: str,
        tool_outputs: list[dict[str, Any]],
    ) -> CitationCheckResult:
        """Extract citations from response and verify against tool outputs.

        Looks for:
        - Explicit citations like "according to..." or "data shows..."
        - Numerical claims that should be backed by data
        - Statements about portfolio data

        Args:
            response: Agent response text
            tool_outputs: List of tool call outputs

        Returns:
            CitationCheckResult with verification details
        """
        # Extract all source data
        source_data = {}
        for i, output in enumerate(tool_outputs):
            source_data[f"tool_{i}"] = output

        # Find citation patterns
        citation_patterns = [
            r"according to ([^,.]+)",
            r"based on ([^,.]+)",
            r"data (?:from|shows) ([^,.]+)",
            r"source:\s*([^,.]+)",
            r"as (?:reported|shown) by ([^,.]+)",
        ]

        citations_found = []
        for pattern in citation_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            citations_found.extend(matches)

        # Extract all numbers from source data for verification
        source_numbers = set()
        self._extract_numbers_from_data(source_data, source_numbers)

        # Find all numerical claims in response
        response_numbers = self._extract_numbers(response)

        # Check which numbers are grounded in source data
        verified_count = 0
        unverified_claims = []

        for num in response_numbers:
            if self._is_number_in_source(num, source_numbers):
                verified_count += 1
            elif num > 100:  # Only flag significant numbers
                # Find the context of this number
                context = self._get_number_context(response, num)
                unverified_claims.append(f"Unverified: {num} ({context})")

        # Calculate accuracy score
        total_significant = sum(1 for n in response_numbers if n > 100)
        if total_significant == 0:
            accuracy_score = 100.0  # No significant numbers to verify
        else:
            accuracy_score = min(100.0, (verified_count / total_significant) * 100)

        result = CitationCheckResult(
            has_citations=len(citations_found) > 0,
            citation_count=len(citations_found),
            verified_citations=verified_count,
            unverified_claims=unverified_claims[:5],  # Limit to top 5
            accuracy_score=round(accuracy_score, 1),
        )

        logger.info(
            f"Citation check: {len(citations_found)} citations, "
            f"{verified_count} verified, accuracy={accuracy_score:.1f}%"
        )

        return result

    async def verify_market_data_freshness(
        self,
        data_timestamp: str | datetime,
        max_age_hours: int = 1,
    ) -> dict[str, Any]:
        """Verify that market data is not stale.

        Args:
            data_timestamp: Timestamp of the data
            max_age_hours: Maximum age in hours before warning

        Returns:
            Verification result with freshness status
        """
        try:
            if isinstance(data_timestamp, str):
                # Parse ISO format timestamp
                timestamp = datetime.fromisoformat(data_timestamp.replace("Z", "+00:00"))
            else:
                timestamp = data_timestamp

            # Make both timezone-naive for comparison
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)

            age = datetime.utcnow() - timestamp
            age_hours = age.total_seconds() / 3600

            is_fresh = age_hours <= max_age_hours

            return {
                "is_fresh": is_fresh,
                "age_hours": round(age_hours, 2),
                "max_age_hours": max_age_hours,
                "warning": None if is_fresh else f"Data is {age_hours:.1f} hours old",
            }

        except (ValueError, TypeError) as e:
            return {
                "is_fresh": False,
                "age_hours": None,
                "max_age_hours": max_age_hours,
                "warning": f"Could not parse timestamp: {e}",
            }

    async def verify_portfolio_totals(
        self,
        claimed_total: float,
        holdings: list[dict[str, Any]],
        tolerance: float | None = None,
    ) -> dict[str, Any]:
        """Verify portfolio total matches sum of holdings.

        Args:
            claimed_total: The claimed portfolio total
            holdings: List of holding dictionaries with values
            tolerance: Acceptable deviation (default uses instance tolerance)

        Returns:
            Verification result
        """
        if tolerance is None:
            tolerance = self.numerical_tolerance

        # Calculate actual total from holdings
        actual_total = sum(
            float(h.get("value", h.get("marketValue", 0)))
            for h in holdings
        )

        if actual_total == 0:
            return {
                "is_accurate": claimed_total == 0,
                "claimed_total": claimed_total,
                "calculated_total": actual_total,
                "difference": claimed_total,
                "explanation": "No holdings to sum",
            }

        diff = abs(claimed_total - actual_total)
        diff_pct = diff / actual_total

        is_accurate = diff_pct <= tolerance

        return {
            "is_accurate": is_accurate,
            "claimed_total": claimed_total,
            "calculated_total": actual_total,
            "difference": round(diff, 2),
            "difference_pct": round(diff_pct * 100, 2),
            "explanation": f"{'Verified' if is_accurate else 'Discrepancy'}: "
                          f"${claimed_total:,.2f} claimed vs ${actual_total:,.2f} calculated",
        }

    def _extract_numbers(self, text: str) -> list[float]:
        """Extract numerical values from text.

        Args:
            text: Text to extract numbers from

        Returns:
            List of numbers found
        """
        matches = re.findall(self.NUMBER_PATTERN, text)
        numbers = []
        for match in matches:
            try:
                num = float(match.replace(',', ''))
                numbers.append(num)
            except ValueError:
                continue
        return numbers

    def _extract_numbers_from_data(
        self,
        data: Any,
        numbers: set[float],
        depth: int = 0,
    ) -> None:
        """Recursively extract numbers from data structure.

        Args:
            data: Data to extract from
            numbers: Set to add found numbers to
            depth: Current recursion depth
        """
        if depth > 6:
            return

        if isinstance(data, (int, float)) and not isinstance(data, bool):
            numbers.add(float(data))
        elif isinstance(data, dict):
            for key, value in data.items():
                # Skip metadata and non-data keys
                if key.startswith("_") or key in ["timestamp", "date", "id", "symbol", "name"]:
                    continue
                self._extract_numbers_from_data(value, numbers, depth + 1)
        elif isinstance(data, list):
            for item in data:
                self._extract_numbers_from_data(item, numbers, depth + 1)

    def _is_number_in_source(
        self,
        claimed: float,
        source_numbers: set[float],
    ) -> bool:
        """Check if a number appears in source data (within tolerance).

        Args:
            claimed: The claimed number
            source_numbers: Set of source numbers

        Returns:
            True if number is found in source (within tolerance)
        """
        if claimed in source_numbers:
            return True

        # Check within tolerance
        for source in source_numbers:
            if source == 0:
                if claimed == 0:
                    return True
            else:
                diff_pct = abs(claimed - source) / abs(source)
                if diff_pct <= self.numerical_tolerance:
                    return True

        return False

    def _get_number_context(self, text: str, number: float, context_chars: int = 30) -> str:
        """Get surrounding context for a number in text.

        Args:
            text: Full text
            number: Number to find context for
            context_chars: Characters of context on each side

        Returns:
            Context string
        """
        # Format number for searching
        num_str = f"{number:,.2f}" if number >= 1000 else str(number)

        # Try different formats
        patterns = [
            num_str,
            f"${num_str}",
            str(int(number)),
        ]

        for pattern in patterns:
            idx = text.find(pattern)
            if idx != -1:
                start = max(0, idx - context_chars)
                end = min(len(text), idx + len(pattern) + context_chars)
                return f"...{text[start:end]}..."

        return "context not found"


__all__ = [
    "FactChecker",
    "FactCheckResult",
    "CitationCheckResult",
]
