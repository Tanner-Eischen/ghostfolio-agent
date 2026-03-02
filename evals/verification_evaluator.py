"""Verification evaluator for the eval framework.

Implements the 4-gate verification system:
1. Syntactic: type, range, nullability checks
2. Temporal: timestamp freshness validation
3. Cross-source: data reconciliation (when possible)
4. Economic-plausibility: business rule validation

Used by eval runner to validate tool outputs beyond simple field presence.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Literal
import math

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Output types supported by the evaluator
OutputType = Literal["quote", "bar", "position", "valuation", "portfolio", "risk", "market_data", "general"]

# Use case thresholds
USE_CASE_THRESHOLDS = {
    "ui_display": 0.5,
    "automated_decision": 0.7,
    "compliance_reporting": 0.9,
}


@dataclass
class GateResult:
    """Result of a single verification gate."""

    gate_name: str
    passed: bool
    evidence: list[str] = field(default_factory=list)
    remediation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "passed": self.passed,
            "evidence": self.evidence,
            "remediation": self.remediation,
        }


@dataclass
class VerificationVerdict:
    """Complete verification verdict for a tool output."""

    gates: dict[str, GateResult] = field(default_factory=dict)
    confidence_score: float = 0.0
    recommended_action: Literal["accept", "accept_with_warning", "quarantine", "escalate"] = "accept"
    remediation_steps: list[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        """Check if all gates passed."""
        return all(g.passed for g in self.gates.values())

    @property
    def passed_count(self) -> int:
        """Count of passed gates."""
        return sum(1 for g in self.gates.values() if g.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gates": {k: v.to_dict() for k, v in self.gates.items()},
            "confidence_score": self.confidence_score,
            "recommended_action": self.recommended_action,
            "remediation_steps": self.remediation_steps,
            "all_passed": self.all_passed,
            "passed_count": self.passed_count,
        }


class VerificationEvaluator:
    """Evaluate tool outputs using the 4-gate verification system."""

    # Staleness thresholds by data type (in seconds)
    STALE_THRESHOLDS = {
        "quote": 300,  # 5 minutes for real-time quotes
        "bar": 86400,  # 24 hours for OHLC bars
        "position": 86400,  # 24 hours for positions
        "valuation": 86400,  # 24 hours for valuations
        "portfolio": 86400,  # 24 hours for portfolio data
        "market_data": 3600,  # 1 hour for general market data
        "risk": 86400,  # 24 hours for risk assessments
        "general": 86400,  # 24 hours default
    }

    def __init__(self, use_case: str = "ui_display"):
        """Initialize the verification evaluator.

        Args:
            use_case: One of 'ui_display', 'automated_decision', 'compliance_reporting'
        """
        self.use_case = use_case
        self.threshold = USE_CASE_THRESHOLDS.get(use_case, 0.5)

    def evaluate_output(
        self,
        output: dict[str, Any],
        output_type: OutputType = "general",
        independent_source: dict[str, Any] | None = None,
    ) -> VerificationVerdict:
        """Evaluate a single tool output through all 4 gates.

        Args:
            output: The tool output to evaluate
            output_type: Type of output for appropriate validation
            independent_source: Optional second source for cross-source verification

        Returns:
            VerificationVerdict with gate results and recommended action
        """
        gates: dict[str, GateResult] = {}

        # Gate 1: Syntactic
        gates["syntactic"] = self._run_syntactic_gate(output, output_type)

        # Gate 2: Temporal
        gates["temporal"] = self._run_temporal_gate(output, output_type)

        # Gate 3: Cross-source (if independent source provided)
        if independent_source:
            gates["cross_source"] = self._run_cross_source_gate(output, independent_source, output_type)
        else:
            # Pass if no independent source to compare against
            gates["cross_source"] = GateResult(
                gate_name="cross_source",
                passed=True,
                evidence=["No independent source provided, gate skipped"],
            )

        # Gate 4: Economic plausibility
        gates["economic_plausibility"] = self._run_economic_plausibility_gate(output, output_type)

        # Calculate confidence score
        passed_count = sum(1 for g in gates.values() if g.passed)
        confidence_score = passed_count / len(gates)

        # Determine recommended action
        if confidence_score >= self.threshold:
            if all(g.passed for g in gates.values()):
                recommended_action = "accept"
            else:
                recommended_action = "accept_with_warning"
        elif confidence_score >= 0.5:
            recommended_action = "quarantine"
        else:
            recommended_action = "escalate"

        # Collect remediation steps
        remediation_steps = []
        for g in gates.values():
            if not g.passed:
                remediation_steps.extend(g.remediation)

        return VerificationVerdict(
            gates=gates,
            confidence_score=confidence_score,
            recommended_action=recommended_action,
            remediation_steps=remediation_steps,
        )

    def _run_syntactic_gate(self, output: dict[str, Any], output_type: OutputType) -> GateResult:
        """Syntactic gate: type, range, nullability checks."""
        evidence = []
        remediation = []
        passed = True

        # Check for error outputs (synthesized structured responses from _parse_tool_output)
        # For error outputs, we accept None values in required fields since the structure is present
        parse_status = output.get("_parse_status", "")
        is_error_output = parse_status in ("auth_error", "timeout_error", "rate_limit_error", "unstructured")
        has_error_field = "error" in output

        # Check for required fields based on output type
        required_fields = self._get_required_fields(output_type)
        for field in required_fields:
            if field not in output:
                passed = False
                evidence.append(f"Missing required field: {field}")
                remediation.append(f"Add field '{field}' to output")
            elif output[field] is None and not is_error_output and not has_error_field:
                # Only fail on None if this is NOT an error output
                passed = False
                evidence.append(f"Field '{field}' is null")
                remediation.append(f"Provide non-null value for '{field}'")

        # Type validation for numeric fields
        numeric_fields = ["price", "value", "total_value", "quantity", "open", "high", "low", "close", "volume"]
        for field in numeric_fields:
            if field in output and output[field] is not None:
                val = output[field]
                if not isinstance(val, (int, float)):
                    passed = False
                    evidence.append(f"Field '{field}' is not numeric: {type(val).__name__}")
                elif math.isnan(val) or math.isinf(val):
                    passed = False
                    evidence.append(f"Field '{field}' has invalid value: {val}")

        # OHLC constraint validation for bar data
        if output_type == "bar":
            o, h, l, c = output.get("open"), output.get("high"), output.get("low"), output.get("close")
            if all(v is not None for v in [o, h, l, c]):
                if h < max(o, c, l):
                    passed = False
                    evidence.append(f"High ({h}) < max(open, close, low)")
                if l > min(o, c, h):
                    passed = False
                    evidence.append(f"Low ({l}) > min(open, close, high)")

        # Range validation for scores
        score_fields = ["confidence", "risk_score", "overall_risk_score", "diversification_score"]
        for field in score_fields:
            if field in output and output[field] is not None:
                val = output[field]
                if isinstance(val, (int, float)) and not (0 <= val <= 100):
                    passed = False
                    evidence.append(f"Score field '{field}' out of range [0-100]: {val}")

        return GateResult(
            gate_name="syntactic",
            passed=passed,
            evidence=evidence,
            remediation=remediation,
        )

    def _run_temporal_gate(self, output: dict[str, Any], output_type: OutputType) -> GateResult:
        """Temporal gate: timestamp presence and freshness."""
        evidence = []
        remediation = []
        passed = True

        # Find timestamp field
        timestamp_fields = ["timestamp", "as_of", "as_of_time", "last_updated", "date", "updated_at"]
        ts_value = None
        ts_field = None

        for field in timestamp_fields:
            if field in output and output[field] is not None:
                ts_value = output[field]
                ts_field = field
                break

        if ts_value is None:
            # For some output types, timestamp is required
            if output_type in ["quote", "bar", "market_data"]:
                passed = False
                evidence.append("No timestamp field found")
                remediation.append("Add timestamp field to output")
            else:
                evidence.append("No timestamp field found (not required for this type)")
            return GateResult(
                gate_name="temporal",
                passed=passed,
                evidence=evidence,
                remediation=remediation,
            )

        # Parse timestamp
        try:
            if isinstance(ts_value, (int, float)):
                ts = datetime.fromtimestamp(ts_value, tz=timezone.utc)
            else:
                ts_str = str(ts_value).replace("Z", "+00:00")
                ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError) as e:
            passed = False
            evidence.append(f"Could not parse timestamp '{ts_value}': {e}")
            remediation.append("Provide timestamp in ISO format")
            return GateResult(
                gate_name="temporal",
                passed=passed,
                evidence=evidence,
                remediation=remediation,
            )

        # Check freshness
        now = datetime.now(timezone.utc)
        age_seconds = (now - ts).total_seconds()
        max_age = self.STALE_THRESHOLDS.get(output_type, 86400)

        if age_seconds < 0:
            evidence.append(f"Timestamp is in the future by {abs(age_seconds):.0f}s")
            # Don't fail for future timestamps (could be clock skew)

        if age_seconds > max_age:
            passed = False
            evidence.append(f"Data is stale: {age_seconds/3600:.1f} hours old (max: {max_age/3600:.1f}h)")
            remediation.append("Refresh data from source")

        evidence.append(f"Data age: {age_seconds:.0f}s (max allowed: {max_age}s)")

        return GateResult(
            gate_name="temporal",
            passed=passed,
            evidence=evidence,
            remediation=remediation,
        )

    def _run_cross_source_gate(
        self,
        output: dict[str, Any],
        independent_source: dict[str, Any],
        output_type: OutputType,
    ) -> GateResult:
        """Cross-source gate: reconcile against independent source."""
        evidence = []
        remediation = []
        passed = True

        # Price tolerance (5 basis points = 0.05%)
        price_tolerance = 0.0005
        # Value tolerance (1%)
        value_tolerance = 0.01

        # Compare price fields
        price_fields = ["price", "last", "close", "value"]
        for field in price_fields:
            if field in output and field in independent_source:
                out_val = output[field]
                src_val = independent_source[field]
                if out_val is not None and src_val is not None:
                    try:
                        out_num = float(out_val)
                        src_num = float(src_val)
                        if src_num != 0:
                            diff_pct = abs(out_num - src_num) / src_num
                            if diff_pct > price_tolerance:
                                passed = False
                                evidence.append(
                                    f"Price mismatch for '{field}': {out_num} vs {src_num} ({diff_pct*100:.2f}% diff)"
                                )
                                remediation.append(f"Reconcile {field} with primary source")
                            else:
                                evidence.append(f"'{field}' matches within tolerance")
                    except (ValueError, TypeError):
                        evidence.append(f"Could not compare {field} values")

        # Compare holdings if portfolio type
        if output_type == "portfolio" and "holdings" in output and "holdings" in independent_source:
            out_symbols = {h.get("symbol") for h in output.get("holdings", []) if isinstance(h, dict)}
            src_symbols = {h.get("symbol") for h in independent_source.get("holdings", []) if isinstance(h, dict)}

            missing = src_symbols - out_symbols
            extra = out_symbols - src_symbols

            if missing:
                passed = False
                evidence.append(f"Missing holdings: {missing}")
                remediation.append("Include all holdings from source")
            if extra:
                evidence.append(f"Additional holdings not in source: {extra}")

        if not evidence:
            evidence.append("Cross-source comparison passed")

        return GateResult(
            gate_name="cross_source",
            passed=passed,
            evidence=evidence,
            remediation=remediation,
        )

    def _run_economic_plausibility_gate(self, output: dict[str, Any], output_type: OutputType) -> GateResult:
        """Economic plausibility gate: business rule validation."""
        evidence = []
        remediation = []
        passed = True

        # No negative prices (unless short position)
        price_fields = ["price", "last", "open", "high", "low", "close", "value", "total_value"]
        for field in price_fields:
            if field in output and output[field] is not None:
                val = output[field]
                if isinstance(val, (int, float)) and val < 0:
                    passed = False
                    evidence.append(f"Negative price/value at '{field}': {val}")
                    remediation.append(f"Ensure '{field}' is non-negative")

        # Bid < Ask check for quotes
        if output_type == "quote":
            bid = output.get("bid")
            ask = output.get("ask")
            if bid is not None and ask is not None:
                if bid > ask:
                    passed = False
                    evidence.append(f"Bid ({bid}) > Ask ({ask})")
                    remediation.append("Fix bid/ask spread")

        # Volume should be non-negative
        if "volume" in output and output["volume"] is not None:
            vol = output["volume"]
            if isinstance(vol, (int, float)) and vol < 0:
                passed = False
                evidence.append(f"Negative volume: {vol}")
                remediation.append("Ensure volume is non-negative")

        # Allocation percentages should be reasonable
        if "holdings" in output and isinstance(output["holdings"], list):
            allocations = []
            for h in output["holdings"]:
                if isinstance(h, dict):
                    alloc = h.get("allocation_pct", h.get("allocationPct"))
                    if alloc is not None:
                        try:
                            alloc_num = float(alloc)
                            allocations.append(alloc_num)
                            if alloc_num < 0 or alloc_num > 100:
                                passed = False
                                evidence.append(f"Invalid allocation for {h.get('symbol')}: {alloc_num}%")
                        except (ValueError, TypeError):
                            pass

            # Check allocations sum
            if allocations:
                total_alloc = sum(allocations)
                if not (99 <= total_alloc <= 101):  # 1% tolerance
                    evidence.append(f"Allocations sum to {total_alloc:.1f}% (expected ~100%)")
                    # Don't fail for this, just warn

        # Concentration check
        if output_type == "portfolio" and "holdings" in output:
            holdings = output["holdings"]
            if isinstance(holdings, list) and len(holdings) > 0:
                max_alloc = 0
                max_symbol = None
                for h in holdings:
                    if isinstance(h, dict):
                        alloc = h.get("allocation_pct", h.get("allocationPct", 0))
                        try:
                            alloc_num = float(alloc)
                            if alloc_num > max_alloc:
                                max_alloc = alloc_num
                                max_symbol = h.get("symbol")
                        except (ValueError, TypeError):
                            pass

                if max_alloc > 50:
                    evidence.append(f"High concentration: {max_alloc:.1f}% in {max_symbol}")
                    # Don't fail, just flag

        if not evidence:
            evidence.append("All economic plausibility checks passed")

        return GateResult(
            gate_name="economic_plausibility",
            passed=passed,
            evidence=evidence,
            remediation=remediation,
        )

    def _get_required_fields(self, output_type: OutputType) -> list[str]:
        """Get required fields for an output type."""
        required = {
            "quote": ["symbol", "price"],
            "bar": ["open", "high", "low", "close"],
            "position": ["symbol", "quantity"],
            "valuation": ["value"],
            "portfolio": ["total_value", "holdings"],
            "risk": ["overall_risk_score"],
            "market_data": ["symbol", "price"],
            "general": [],
        }
        return required.get(output_type, [])


__all__ = [
    "VerificationEvaluator",
    "VerificationVerdict",
    "GateResult",
    "OutputType",
]
