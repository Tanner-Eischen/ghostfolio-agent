"""Verification module - Response validation and confidence scoring.

This module provides comprehensive verification of agent responses:

1. **ConfidenceScorer** - Calculates confidence scores based on:
   - Data completeness
   - Tool success rate
   - Response grounding

2. **FactChecker** - Verifies factual claims:
   - Cross-references with tool outputs
   - Numerical accuracy checking
   - Citation verification

3. **ConstraintValidator** - Validates domain constraints:
   - Financial constraints (no negative values)
   - Data constraints (valid dates, symbols)
   - Business rules (allocation sums, risk thresholds)

4. **VerificationPipeline** - Orchestrates all verification:
   - Runs all checks in sequence
   - Generates comprehensive reports
   - Determines escalation needs

Example usage:
    ```python
    from src.verification import VerificationPipeline

    pipeline = VerificationPipeline()
    report = await pipeline.verify(
        response="Your portfolio is worth $100,000",
        tool_outputs=[{"total_value": 100000}],
        query="What's my portfolio worth?"
    )

    if report.passed:
        print(f"Verification passed with {report.confidence_score}% confidence")
    else:
        print(f"Verification failed: {report.violations}")
    ```
"""

from src.verification.confidence import (
    ConfidenceAssessment,
    ConfidenceScorer,
    ESCALATION_THRESHOLD,
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
    MEDIUM_THRESHOLD,
    VERY_HIGH_THRESHOLD,
)
from src.verification.constraints import (
    ConstraintValidationResult,
    ConstraintValidator,
    ConstraintViolation,
)
from src.verification.fact_checker import (
    CitationCheckResult,
    FactCheckResult,
    FactChecker,
)
from src.verification.pipeline import (
    EscalationStatus,
    VerificationPipeline,
    VerificationReport,
)

__all__ = [
    # Main pipeline
    "VerificationPipeline",
    "VerificationReport",
    "EscalationStatus",
    # Confidence scoring
    "ConfidenceScorer",
    "ConfidenceAssessment",
    "ESCALATION_THRESHOLD",
    "VERY_HIGH_THRESHOLD",
    "HIGH_THRESHOLD",
    "MEDIUM_THRESHOLD",
    "LOW_THRESHOLD",
    # Fact checking
    "FactChecker",
    "FactCheckResult",
    "CitationCheckResult",
    # Constraint validation
    "ConstraintValidator",
    "ConstraintViolation",
    "ConstraintValidationResult",
]
