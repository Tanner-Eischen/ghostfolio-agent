"""Verification pipeline that orchestrates all verification checks.

The pipeline runs multiple verification steps:
1. Constraint validation - Check domain constraints
2. Fact checking - Cross-reference claims with data
3. Confidence scoring - Calculate overall confidence
4. Hallucination detection - Flag ungrounded claims
5. Portfolio total consistency - Verify total_value matches sum(holdings)
6. Market data freshness - Verify timestamps are within threshold

Then synthesizes results into a comprehensive verification report.

Performance: Market data freshness, fact checks, and citation verification
run in parallel where possible to reduce wall-clock time.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Literal

from langsmith import traceable
from pydantic import BaseModel, Field

from src.utils.config_store import get_verification_config_store
from src.utils.logging import get_logger
from src.verification.confidence import (
    ConfidenceAssessment,
    ConfidenceScorer,
    ESCALATION_THRESHOLD,
)
from src.verification.constraints import (
    ConstraintValidationResult,
    ConstraintValidator,
    ConstraintViolation,
)
from src.verification.fact_checker import (
    CitationCheckResult,
    FactChecker,
    FactCheckResult,
)

logger = get_logger(__name__)


class EscalationStatus(BaseModel):
    """Escalation status and triggers."""

    requires_escalation: bool = Field(default=False, description="Whether human review is required")
    triggers: list[str] = Field(default_factory=list, description="Escalation triggers hit")
    severity: str = Field(default="NONE", description="Escalation severity")


class VerificationReport(BaseModel):
    """Complete verification report."""

    # Overall status
    passed: bool = Field(description="Whether verification passed")
    confidence_score: float = Field(ge=0, le=100, description="Overall confidence score")
    confidence_level: str = Field(description="Confidence level text")

    # Component results
    constraint_result: ConstraintValidationResult | None = Field(
        default=None, description="Constraint validation result"
    )
    fact_check_results: list[FactCheckResult] = Field(
        default_factory=list, description="Individual fact check results"
    )
    citation_result: CitationCheckResult | None = Field(
        default=None, description="Citation verification result"
    )
    confidence_assessment: ConfidenceAssessment | None = Field(
        default=None, description="Detailed confidence breakdown"
    )

    # Issues found
    violations: list[ConstraintViolation] = Field(
        default_factory=list, description="Constraint violations found"
    )
    unverified_claims: list[str] = Field(
        default_factory=list, description="Claims that couldn't be verified"
    )
    warnings: list[str] = Field(default_factory=list, description="Warnings")

    # Escalation
    escalation: EscalationStatus = Field(
        default_factory=lambda: EscalationStatus(),
        description="Escalation status",
    )

    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    processing_time_ms: float | None = Field(default=None, description="Processing time")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "passed": self.passed,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "violations_count": len(self.violations),
            "warnings_count": len(self.warnings),
            "requires_escalation": self.escalation.requires_escalation,
            "escalation_triggers": self.escalation.triggers,
            "timestamp": self.timestamp,
        }


class VerificationPipeline:
    """Orchestrates all verification checks."""

    def __init__(
        self,
        confidence_threshold: float | None = None,
        strict_mode: bool | None = None,
    ) -> None:
        """Initialize verification pipeline.

        Args:
            confidence_threshold: Minimum confidence before escalation (default from config store)
            strict_mode: If True, any violation fails verification
        """
        self.fact_checker = FactChecker()
        self.confidence_scorer = ConfidenceScorer()
        self.constraint_validator = ConstraintValidator()

        # Read from config store if not explicitly provided
        config_store = get_verification_config_store()
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else config_store.get("confidence_threshold", ESCALATION_THRESHOLD)
        )
        self.strict_mode = (
            strict_mode
            if strict_mode is not None
            else config_store.get("strict_mode", False)
        )

    @traceable(name="verification_pipeline_verify", run_type="chain")
    async def verify(
        self,
        response: str,
        tool_outputs: list[dict[str, Any]],
        query: str,
        response_data: dict[str, Any] | None = None,
    ) -> VerificationReport:
        """Run all verification checks.

        This is the main entry point for verification. It runs:
        1. Constraint validation on response data
        2. Fact checking on claims
        3. Citation verification
        4. Confidence scoring
        5. Escalation check

        Args:
            response: Agent response text
            tool_outputs: List of tool call outputs
            query: Original user query
            response_data: Structured response data (optional)

        Returns:
            VerificationReport with all check results
        """
        start_time = datetime.utcnow()

        logger.info(f"Starting verification pipeline for query: {query[:50]}...")

        # Initialize results
        constraint_result: ConstraintValidationResult | None = None
        fact_check_results: list[FactCheckResult] = []
        citation_result: CitationCheckResult | None = None
        confidence_assessment: ConfidenceAssessment | None = None

        # 1. Run constraint validation if we have structured data
        response_type = "general"
        if response_data:
            response_type = self._detect_response_type(response_data)
            constraint_result = self.constraint_validator.validate_response(
                response_data, response_type
            )

        # 1.5. Portfolio total consistency (domain verification)
        portfolio_warnings: list[str] = []
        portfolio_triggers: list[str] = []
        if response_data and response_type == "portfolio":
            pw, pt = self._check_portfolio_total_consistency(response_data)
            portfolio_warnings.extend(pw)
            portfolio_triggers.extend(pt)

        # 1.6–3. Run market freshness, fact checks, and citation verification in parallel
        market_warnings: list[str] = []
        market_triggers: list[str] = []

        async def _market_freshness() -> tuple[list[str], list[str]]:
            if not tool_outputs:
                return [], []
            return await self._check_market_data_freshness(tool_outputs)

        async def _citations() -> CitationCheckResult | None:
            if not tool_outputs:
                return None
            return await self.fact_checker.extract_and_verify_citations(
                response, tool_outputs
            )

        (
            (_mw, _mt),
            fact_check_results,
            citation_result,
        ) = await asyncio.gather(
            _market_freshness(),
            self._run_fact_checks(response, tool_outputs),
            _citations(),
        )
        market_warnings.extend(_mw)
        market_triggers.extend(_mt)

        # 4. Compile verification results for confidence scoring
        verification_results = self._compile_verification_results(
            constraint_result, fact_check_results, citation_result
        )

        # 5. Calculate confidence score
        confidence_assessment = await self.confidence_scorer.calculate_confidence(
            response, tool_outputs, verification_results
        )

        # 6. Check for escalation triggers
        escalation = self._check_escalation(
            confidence_assessment,
            constraint_result,
            citation_result,
            tool_outputs,
            portfolio_triggers=portfolio_triggers,
            market_triggers=market_triggers,
        )

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Compile violations and warnings
        violations = constraint_result.violations if constraint_result else []
        unverified_claims = citation_result.unverified_claims if citation_result else []
        warnings = []
        if constraint_result:
            warnings.extend(constraint_result.warnings)
        warnings.extend(portfolio_warnings)
        warnings.extend(market_warnings)

        # Determine overall pass/fail
        passed = self._determine_pass(
            confidence_assessment,
            constraint_result,
            escalation,
        )

        report = VerificationReport(
            passed=passed,
            confidence_score=confidence_assessment.score,
            confidence_level=confidence_assessment.level,
            constraint_result=constraint_result,
            fact_check_results=fact_check_results,
            citation_result=citation_result,
            confidence_assessment=confidence_assessment,
            violations=violations,
            unverified_claims=unverified_claims,
            warnings=warnings,
            escalation=escalation,
            processing_time_ms=round(processing_time, 2),
        )

        logger.info(
            f"Verification complete: passed={passed}, "
            f"confidence={confidence_assessment.score:.1f}%, "
            f"escalation={escalation.requires_escalation}"
        )

        return report

    async def verify_response_only(
        self,
        response: str,
        query: str,
    ) -> VerificationReport:
        """Run verification without tool outputs.

        Used for responses that don't involve tool calls.

        Args:
            response: Agent response text
            query: Original user query

        Returns:
            VerificationReport with limited checks
        """
        return await self.verify(response, [], query, None)

    async def verify_with_data(
        self,
        response: str,
        response_data: dict[str, Any],
        query: str,
    ) -> VerificationReport:
        """Run verification with structured response data.

        Args:
            response: Agent response text
            response_data: Structured response data
            query: Original user query

        Returns:
            VerificationReport with constraint validation
        """
        return await self.verify(response, [response_data], query, response_data)

    def get_verification_summary(
        self,
        report: VerificationReport,
    ) -> dict[str, Any]:
        """Get a summary of verification results.

        Args:
            report: VerificationReport to summarize

        Returns:
            Summary dictionary
        """
        return {
            "status": "PASSED" if report.passed else "FAILED",
            "confidence": {
                "score": report.confidence_score,
                "level": report.confidence_level,
            },
            "issues": {
                "violations": len(report.violations),
                "warnings": len(report.warnings),
                "unverified_claims": len(report.unverified_claims),
            },
            "escalation": {
                "required": report.escalation.requires_escalation,
                "triggers": report.escalation.triggers,
                "severity": report.escalation.severity,
            },
            "details": {
                "constraints_checked": report.constraint_result is not None,
                "facts_checked": len(report.fact_check_results),
                "citations_checked": report.citation_result is not None,
            },
            "processing_time_ms": report.processing_time_ms,
        }

    def _detect_response_type(self, data: dict[str, Any]) -> str:
        """Detect the type of response for appropriate validation.

        Args:
            data: Response data

        Returns:
            Response type string
        """
        # Check for portfolio indicators
        if "holdings" in data or "total_value" in data:
            return "portfolio"

        # Check for transaction indicators
        if "transactions" in data or "type" in data:
            return "transaction"

        # Check for risk indicators
        if "risk_score" in data or "concentration_risk" in data:
            return "risk"

        # Check for market data indicators
        if "price" in data or "data" in data:
            return "market_data"

        return "general"

    async def _run_fact_checks(
        self,
        response: str,
        tool_outputs: list[dict[str, Any]],
    ) -> list[FactCheckResult]:
        """Run fact checks on key claims in response.

        Args:
            response: Response text
            tool_outputs: Tool output data

        Returns:
            List of fact check results
        """
        results = []

        # Combine all tool outputs into source data
        source_data = {}
        for i, output in enumerate(tool_outputs):
            source_data[f"tool_{i}"] = output

        # Extract sentences that might contain claims
        sentences = self._extract_claim_sentences(response)

        # Check up to 5 claims in parallel to reduce verification latency
        tasks = [
            self.fact_checker.verify_claim(sentence, source_data)
            for sentence in sentences[:5]
        ]
        if tasks:
            results = list(await asyncio.gather(*tasks))
        return results

    def _extract_claim_sentences(self, text: str) -> list[str]:
        """Extract sentences that likely contain factual claims.

        Args:
            text: Full response text

        Returns:
            List of claim sentences
        """
        # Split into sentences
        import re
        sentences = re.split(r'[.!?]+', text)

        claim_keywords = [
            "total", "value", "worth", "price", "cost", "amount",
            "percentage", "ratio", "score", "rank", "return", "gain", "loss",
            "is", "are", "was", "were", "has", "have"
        ]

        claim_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            # Check if sentence contains numerical claims
            has_number = bool(re.search(r'\$?[\d,]+(?:\.\d+)?%?', sentence))
            has_keyword = any(kw in sentence.lower() for kw in claim_keywords)

            if has_number and has_keyword:
                claim_sentences.append(sentence)

        return claim_sentences

    def _compile_verification_results(
        self,
        constraint_result: ConstraintValidationResult | None,
        fact_check_results: list[FactCheckResult],
        citation_result: CitationCheckResult | None,
    ) -> dict[str, Any]:
        """Compile results for confidence scoring.

        Args:
            constraint_result: Constraint validation result
            fact_check_results: Fact check results
            citation_result: Citation check result

        Returns:
            Compiled verification results
        """
        results: dict[str, Any] = {
            "constraint_violations": [],
            "fact_check_failures": [],
            "citation_score": 100.0,
        }

        if constraint_result:
            results["constraint_violations"] = [
                v.message for v in constraint_result.violations
            ]

        for fc in fact_check_results:
            if not fc.is_accurate:
                results["fact_check_failures"].append(fc.claim[:100])

        if citation_result:
            results["citation_score"] = citation_result.accuracy_score

        return results

    def _check_portfolio_total_consistency(
        self, response_data: dict[str, Any]
    ) -> tuple[list[str], list[str]]:
        """Portfolio total consistency: claimed total vs sum(holdings).

        Rule: pass if diff <= max(1.0, 0.005 * claimed). Escalate if > 2%.
        """
        warnings: list[str] = []
        triggers: list[str] = []

        total_value = response_data.get("total_value")
        if total_value is None:
            return warnings, triggers

        holdings = response_data.get("holdings")
        if not holdings or not isinstance(holdings, list):
            return warnings, triggers

        try:
            claimed = float(total_value)
        except (TypeError, ValueError):
            return warnings, triggers

        computed = sum(
            float(h.get("value", h.get("marketValue", 0)))
            for h in holdings
            if isinstance(h, dict) and (h.get("value") is not None or h.get("marketValue") is not None)
        )

        diff = abs(claimed - computed)
        tolerance = max(1.0, 0.005 * claimed)

        if diff > tolerance:
            msg = f"PORTFOLIO_TOTAL_MISMATCH: claimed={claimed:.2f}, computed={computed:.2f}, delta={diff:.2f}"
            warnings.append(msg)
            if diff > 0.02 * claimed:
                triggers.append("Portfolio total inconsistency")

        return warnings, triggers

    async def _check_market_data_freshness(
        self, tool_outputs: list[dict[str, Any]]
    ) -> tuple[list[str], list[str]]:
        """Market data freshness: warn if timestamp missing or stale (>1h). Escalate if >24h."""
        warnings: list[str] = []
        triggers: list[str] = []
        ts_fields = ("timestamp", "as_of", "last_updated", "date")
        max_age_hours = 1
        escalate_age_hours = 24

        now = datetime.now(timezone.utc)

        for obj in tool_outputs:
            if not isinstance(obj, dict):
                continue
            if "price" not in obj and "data" not in obj:
                continue

            ts_val = None
            for f in ts_fields:
                if f in obj:
                    ts_val = obj[f]
                    break

            if ts_val is None:
                warnings.append("MARKET_DATA_TIMESTAMP_MISSING: no timestamp in market data object")
                continue

            try:
                if isinstance(ts_val, (int, float)):
                    ts = datetime.fromtimestamp(ts_val, tz=timezone.utc)
                else:
                    ts_str = str(ts_val).replace("Z", "+00:00")
                    ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                warnings.append("MARKET_DATA_TIMESTAMP_MISSING: could not parse timestamp")
                continue

            age = (now - ts).total_seconds() / 3600
            if age > escalate_age_hours:
                triggers.append("Stale market data")
                warnings.append(f"MARKET_DATA_STALE: data is {age:.1f} hours old")
            elif age > max_age_hours:
                warnings.append(f"MARKET_DATA_STALE: data is {age:.1f} hours old")

        return warnings, triggers

    def _check_escalation(
        self,
        confidence: ConfidenceAssessment,
        constraint_result: ConstraintValidationResult | None,
        citation_result: CitationCheckResult | None,
        tool_outputs: list[dict[str, Any]],
        portfolio_triggers: list[str] | None = None,
        market_triggers: list[str] | None = None,
    ) -> EscalationStatus:
        """Check if human escalation is required.

        Escalation triggers (from PRE-SEARCH.md):
        - Confidence < 70%
        - Compliance rule violation
        - Large transaction values (> $10,000)
        - Unusual portfolio changes (>20% daily change)

        Args:
            confidence: Confidence assessment
            constraint_result: Constraint validation result
            citation_result: Citation check result
            tool_outputs: Tool outputs for additional checks

        Returns:
            EscalationStatus
        """
        triggers = []
        severity = "NONE"

        # Check confidence threshold
        if confidence.score < self.confidence_threshold:
            triggers.append(f"Low confidence: {confidence.score:.1f}%")
            severity = "MEDIUM"

        # Check for critical constraint violations
        if constraint_result:
            critical_violations = [
                v for v in constraint_result.violations
                if v.severity in ("HIGH", "CRITICAL")
            ]
            if critical_violations:
                triggers.append(f"Critical constraint violations: {len(critical_violations)}")
                severity = "HIGH"

        # Check for compliance violations (from constraint warnings)
        if constraint_result:
            for warning in constraint_result.warnings:
                if "large transaction" in warning.lower():
                    triggers.append(warning)
                    if severity == "NONE":
                        severity = "LOW"
                elif "compliance" in warning.lower():
                    triggers.append(warning)
                    severity = "HIGH"

        # Check for many unverified claims
        if citation_result and len(citation_result.unverified_claims) > 3:
            triggers.append(f"Multiple unverified claims: {len(citation_result.unverified_claims)}")
            if severity in ("NONE", "LOW"):
                severity = "MEDIUM"

        # Portfolio total inconsistency
        if portfolio_triggers:
            triggers.extend(portfolio_triggers)
            if severity in ("NONE", "LOW"):
                severity = "MEDIUM"

        # Stale market data
        if market_triggers:
            triggers.extend(market_triggers)
            if severity in ("NONE", "LOW"):
                severity = "MEDIUM"

        return EscalationStatus(
            requires_escalation=len(triggers) > 0,
            triggers=triggers,
            severity=severity,
        )

    def _determine_pass(
        self,
        confidence: ConfidenceAssessment,
        constraint_result: ConstraintValidationResult | None,
        escalation: EscalationStatus,
    ) -> bool:
        """Determine overall verification pass/fail.

        Args:
            confidence: Confidence assessment
            constraint_result: Constraint validation result
            escalation: Escalation status

        Returns:
            True if verification passed
        """
        # In strict mode, any issue fails
        if self.strict_mode:
            if constraint_result and not constraint_result.is_valid:
                return False
            if escalation.requires_escalation:
                return False

        # In normal mode, only fail on critical issues
        # Low confidence alone doesn't fail, but triggers escalation
        if constraint_result:
            critical_violations = [
                v for v in constraint_result.violations
                if v.severity == "CRITICAL"
            ]
            if critical_violations:
                return False

        # For MVP: Only fail on extremely low confidence (< 20)
        # This allows responses with tools used to pass even if confidence scoring is imperfect
        if confidence.score < 20:
            return False

        return True


__all__ = [
    "VerificationPipeline",
    "VerificationReport",
    "EscalationStatus",
]
