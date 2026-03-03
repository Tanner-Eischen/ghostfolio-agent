"""Pydantic models for Ghostfolio Agent API.

This module contains all request and response models used by the API endpoints.
Organized by domain for easier navigation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Chat Models
# =============================================================================


class ChatRequest(BaseModel):
    """Chat request model."""

    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    session_id: str | None = Field(None, description="Session ID for conversation continuity")
    user_id: str | None = Field(None, description="Optional user identifier")


class ChatResponse(BaseModel):
    """Chat response model."""

    response: str = Field(..., description="Agent response text")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score (0-100)")
    confidence_level: str = Field(..., description="Confidence level label")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="Tools invoked")
    tool_outputs: list[Any] = Field(default_factory=list, description="Tool execution results")
    tool_invocations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Detailed tool invocations with call and output",
    )
    session_id: str = Field(..., description="Session ID for conversation continuity")
    verification_passed: bool = Field(..., description="Whether verification passed")
    requires_escalation: bool = Field(
        default=False,
        description="Whether human escalation is recommended",
    )
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    run_id: str | None = Field(None, description="LangSmith run ID for tracing")
    trace_url: str | None = Field(None, description="LangSmith trace URL")


# =============================================================================
# System Models
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Deployment environment")
    timestamp: str = Field(..., description="Current server time (ISO 8601)")
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description="Status of external dependencies",
    )


# =============================================================================
# Feedback Models
# =============================================================================


class FeedbackRequest(BaseModel):
    """Feedback submission request."""

    message_id: str = Field(..., description="ID of the message being rated")
    session_id: str | None = Field(None, description="Session ID for context")
    rating: int = Field(..., ge=-1, le=5, description="Rating: -1 (thumbs down), 1 (thumbs up), or 1-5 stars")
    comment: str | None = Field(None, max_length=1000, description="Optional feedback comment")


class FeedbackResponse(BaseModel):
    """Feedback submission response."""

    status: str = Field(..., description="Submission status")
    message_id: str = Field(..., description="ID of the rated message")
    logged: bool = Field(..., description="Whether feedback was logged successfully")


# =============================================================================
# Portfolio Models
# =============================================================================


class PortfolioSummaryResponse(BaseModel):
    """Portfolio summary response model."""

    total_value: float | None = Field(None, description="Total portfolio value")
    performance_ytd: float | None = Field(None, description="Year-to-date performance percentage")
    holdings_count: int = Field(..., description="Number of holdings")
    top_holdings: list[dict[str, Any]] = Field(default_factory=list, description="Top 5 holdings")
    diversification_score: float | None = Field(None, description="Diversification score (0-100)")
    risk_level: str | None = Field(None, description="Risk level assessment")


# =============================================================================
# Session Models
# =============================================================================


class SessionSummary(BaseModel):
    """Session summary model."""

    session_id: str = Field(..., description="Session ID")
    message_count: int = Field(..., description="Number of messages in session")
    created_at: str = Field(..., description="Session creation time")
    last_activity: str = Field(..., description="Last activity time")


class SessionsListResponse(BaseModel):
    """Sessions list response model."""

    sessions: list[SessionSummary] = Field(default_factory=list, description="List of sessions")
    total: int = Field(..., description="Total number of sessions")


class SessionHistoryResponse(BaseModel):
    """Session history response model."""

    session_id: str = Field(..., description="Session ID")
    messages: list[dict[str, Any]] = Field(default_factory=list, description="Conversation history")
    created_at: str = Field(..., description="Session creation time")


# =============================================================================
# Error Models
# =============================================================================


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: str | None = Field(None, description="Detailed error information")


# =============================================================================
# Agent Models
# =============================================================================


class AgentConfigResponse(BaseModel):
    """Agent configuration response."""

    model: str = Field(..., description="Current LLM model id (e.g. gpt-4o-mini)")
    allowed_models: list[str] = Field(
        default_factory=lambda: [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ],
        description="Model ids that can be selected",
    )


class AgentConfigRequest(BaseModel):
    """Agent configuration update request."""

    model: str = Field(..., description="LLM model id to use")


# =============================================================================
# Strategy Models
# =============================================================================


class StrategyConfigResponse(BaseModel):
    """Strategy configuration response."""

    framework: str = Field(default="LangGraph", description="Selected framework")
    model: str = Field(default="GPT-4o (OpenAI)", description="Selected model")
    temperature: float = Field(default=0.0, description="Model temperature")
    json_mode: bool = Field(default=True, description="JSON mode enabled")
    stream_responses: bool = Field(default=False, description="Stream responses")
    contribution_path: str = Field(default="langchain", description="Contribution path")


class StrategyRecommendationResponse(BaseModel):
    """Strategy recommendation response."""

    framework: str = Field(..., description="Framework name")
    reason: str = Field(..., description="Recommendation reason")
    recommended: bool = Field(..., description="Is recommended")


# =============================================================================
# Tools Models
# =============================================================================


class ToolResponse(BaseModel):
    """Tool response model."""

    id: str = Field(..., description="Tool ID")
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    status: str = Field(default="active", description="Tool status")


class ToolCreateRequest(BaseModel):
    """Tool creation request."""

    name: str = Field(..., min_length=1, max_length=100, description="Tool name")
    description: str = Field(..., min_length=1, max_length=500, description="Tool description")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")


class ToolRegistrationRequest(BaseModel):
    """Tool registration request for generated tools."""

    name: str = Field(..., min_length=1, max_length=100, description="Tool name")
    description: str = Field(..., min_length=1, description="Tool description")
    generated_code: str = Field(..., min_length=1, description="Generated Python code for the tool")
    source_suggestion_id: str | None = Field(None, description="ID of the suggestion that generated this tool")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")


class ToolRegistrationResponse(BaseModel):
    """Tool registration response."""

    success: bool = Field(..., description="Whether registration succeeded")
    message: str = Field(..., description="Status message")
    tool_name: str | None = Field(None, description="Registered tool name")
    tool_id: str | None = Field(None, description="Registered tool ID")
    warnings: list[str] = Field(default_factory=list, description="Any warnings during registration")
    agent_reloaded: bool = Field(default=False, description="Whether agent was reloaded")


class ToolDetailResponse(BaseModel):
    """Tool detail response model."""

    id: str = Field(..., description="Tool ID")
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    status: str = Field(default="active", description="Tool status")
    source: str = Field(default="core", description="Tool source (core or generated)")
    created_at: str | None = Field(None, description="Tool creation time")


class ToolExecuteRequest(BaseModel):
    """Tool execution request."""

    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class ToolExecuteResponse(BaseModel):
    """Tool execution response."""

    tool_name: str = Field(..., description="Tool name")
    success: bool = Field(..., description="Whether execution succeeded")
    result: dict[str, Any] | None = Field(None, description="Execution result")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")


# =============================================================================
# Verification Models
# =============================================================================


class VerificationConfigResponse(BaseModel):
    """Verification configuration response."""

    fact_checking: bool = Field(default=True, description="Fact checking enabled")
    hallucination_detection: bool = Field(default=True, description="Hallucination detection enabled")
    confidence_scoring: bool = Field(default=True, description="Confidence scoring enabled")
    hitl_enabled: bool = Field(default=False, description="Human-in-the-loop enabled")
    confidence_threshold: int = Field(default=70, description="Confidence threshold (0-100)")
    strict_mode: bool = Field(default=False, description="Strict mode (fail on any issue)")


# =============================================================================
# Trace Models
# =============================================================================


class TraceResponse(BaseModel):
    """Trace response model."""

    id: str = Field(..., description="Trace ID")
    name: str = Field(..., description="Trace name")
    start_time: str = Field(..., description="Start time")
    end_time: str | None = Field(None, description="End time")
    status: str = Field(..., description="Trace status")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Inputs")
    outputs: dict[str, Any] = Field(default_factory=dict, description="Outputs")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata")
    total_tokens: int = Field(default=0, description="Total tokens used")
    total_cost_usd: float | None = Field(None, description="Estimated cost in USD")


class TraceDetailResponse(BaseModel):
    """Detailed trace response model."""

    id: str = Field(..., description="Trace ID")
    name: str = Field(..., description="Trace name")
    start_time: str = Field(..., description="Start time")
    end_time: str | None = Field(None, description="End time")
    status: str = Field(..., description="Trace status")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Inputs")
    outputs: dict[str, Any] = Field(default_factory=dict, description="Outputs")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata")
    total_tokens: int = Field(default=0, description="Total tokens used")
    total_cost_usd: float | None = Field(None, description="Estimated cost in USD")
    child_runs: list[dict[str, Any]] = Field(default_factory=list, description="Child runs")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="Tool calls")


# =============================================================================
# Eval Models
# =============================================================================


class EvalCaseResponse(BaseModel):
    """Eval case response model."""

    id: str = Field(..., description="Case ID")
    name: str = Field(..., description="Case name")
    description: str = Field(..., description="Case description")
    category: str = Field(..., description="Case category")


class EvalResultResponse(BaseModel):
    """Eval result response model."""

    case_id: str = Field(..., description="Case ID")
    passed: bool = Field(..., description="Whether the case passed")
    score: float = Field(..., description="Score (0-1)")
    duration_ms: float = Field(..., description="Duration in milliseconds")
    error: str | None = Field(None, description="Error message if failed")


class EvalSummaryResponse(BaseModel):
    """Eval summary response model."""

    total_cases: int = Field(..., description="Total number of cases")
    passed: int = Field(..., description="Number of passed cases")
    failed: int = Field(..., description="Number of failed cases")
    pass_rate: float = Field(..., description="Pass rate (0-1)")
    avg_latency_ms: float = Field(..., description="Average latency in milliseconds")
    hallucination_rate: float = Field(..., description="Hallucination rate (0-1)")


class EvalResultsResponse(BaseModel):
    """Eval results response model."""

    summary: EvalSummaryResponse = Field(..., description="Summary statistics")
    results: list[EvalResultResponse] = Field(default_factory=list, description="Individual results")


class EvalRunRequest(BaseModel):
    """Eval run request model."""

    config: dict[str, Any] | None = Field(None, description="Optional config overrides")


# =============================================================================
# Finances Models
# =============================================================================


class UsageByModel(BaseModel):
    """Usage by model response."""

    model: str = Field(..., description="Model name")
    input_tokens: int = Field(default=0, description="Input tokens")
    output_tokens: int = Field(default=0, description="Output tokens")
    total_tokens: int = Field(default=0, description="Total tokens")
    cost_usd: float = Field(default=0.0, description="Cost in USD")


class UsageStatsResponse(BaseModel):
    """Usage stats response model."""

    total_requests: int = Field(default=0, description="Total requests")
    total_tokens: int = Field(default=0, description="Total tokens")
    total_cost_usd: float = Field(default=0.0, description="Total cost in USD")
    by_model: list[UsageByModel] = Field(default_factory=list, description="Usage by model")
    period_start: str | None = Field(None, description="Period start time")
    period_end: str | None = Field(None, description="Period end time")


class CostProjectionsResponse(BaseModel):
    """Cost projections response model."""

    daily_cost_usd: float = Field(..., description="Daily cost projection")
    monthly_cost_usd: float = Field(..., description="Monthly cost projection")
    yearly_cost_usd: float = Field(..., description="Yearly cost projection")
    requests_per_day: int = Field(..., description="Estimated requests per day")


class ModelPricingEntry(BaseModel):
    """Model pricing entry."""

    model: str = Field(..., description="Model name")
    input_cost_per_1k: float = Field(..., description="Input cost per 1K tokens")
    output_cost_per_1k: float = Field(..., description="Output cost per 1K tokens")


class ModelPricingResponse(BaseModel):
    """Model pricing response."""

    models: list[ModelPricingEntry] = Field(default_factory=list, description="Model pricing")


class CostComparisonEntry(BaseModel):
    """Cost comparison entry."""

    model: str = Field(..., description="Model name")
    estimated_monthly_cost_usd: float = Field(..., description="Estimated monthly cost")
    input_cost_per_1k: float = Field(..., description="Input cost per 1K tokens")
    output_cost_per_1k: float = Field(..., description="Output cost per 1K tokens")
    notes: str | None = Field(None, description="Additional notes")


class CostComparisonResponse(BaseModel):
    """Cost comparison response."""

    current_model: str = Field(..., description="Current model")
    current_monthly_cost_usd: float = Field(..., description="Current monthly cost")
    comparisons: list[CostComparisonEntry] = Field(default_factory=list, description="Model comparisons")


class SeedDemoUsageResponse(BaseModel):
    """Seed demo usage response."""

    status: str = Field(..., description="Status message")
    records_created: int = Field(..., description="Number of records created")


# =============================================================================
# Constants
# =============================================================================

# Allowed LLM models for agent (OpenAI models supported by ChatOpenAI)
ALLOWED_AGENT_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
]
