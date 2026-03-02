"""Central exception hierarchy for Ghostfolio Agent.

This module provides domain-specific exceptions for better error handling,
more precise error messages, and easier debugging.

Exception Hierarchy:
    GhostfolioAgentError (base)
    ├── APIError
    │   ├── AuthenticationError
    │   ├── RateLimitError
    │   ├── ResourceNotFoundError
    │   ├── ConnectionError
    │   └── TimeoutError
    ├── LLMError
    │   ├── InvalidAPIKeyError
    │   ├── ModelNotAvailableError
    │   └── ContentFilterError
    ├── ToolError
    │   ├── ToolValidationError
    │   └── ToolExecutionError
    └── ConfigurationError
"""

from typing import Any


class GhostfolioAgentError(Exception):
    """Base exception for all Ghostfolio Agent errors.

    All custom exceptions in the project should inherit from this class
    to allow for broad exception catching when needed.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


# =============================================================================
# API Errors - External service communication errors
# =============================================================================


class APIError(GhostfolioAgentError):
    """Base exception for API-related errors.

    Use when communicating with external services like Ghostfolio API,
    CoinGecko, Yahoo Finance, etc.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.status_code = status_code


class AuthenticationError(APIError):
    """Raised when authentication fails with an external service.

    Common causes:
    - Invalid or expired access token
    - Missing authentication credentials
    - Insufficient permissions
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        service: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=401, details=details)
        self.service = service


class RateLimitError(APIError):
    """Raised when rate limited by an external service.

    Common causes:
    - Too many requests in a short time period
    - Exceeded API quota
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        service: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=429, details=details)
        self.retry_after = retry_after
        self.service = service


class ResourceNotFoundError(APIError):
    """Raised when a requested resource is not found.

    Common causes:
    - Invalid symbol or asset ID
    - Portfolio or position doesn't exist
    - Endpoint not found
    """

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=404, details=details)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ConnectionError(APIError):
    """Raised when unable to connect to an external service.

    Common causes:
    - Network connectivity issues
    - DNS resolution failure
    - Service unavailable
    """

    def __init__(
        self,
        message: str = "Failed to connect to service",
        service: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=503, details=details)
        self.service = service


class TimeoutError(APIError):
    """Raised when a request times out.

    Common causes:
    - Slow network connection
    - Overloaded external service
    - Request too large
    """

    def __init__(
        self,
        message: str = "Request timed out",
        timeout_seconds: float | None = None,
        service: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=504, details=details)
        self.timeout_seconds = timeout_seconds
        self.service = service


# =============================================================================
# LLM Errors - Language model related errors
# =============================================================================


class LLMError(GhostfolioAgentError):
    """Base exception for LLM-related errors.

    Use when there are issues with OpenAI or other LLM providers.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.provider = provider


class InvalidAPIKeyError(LLMError):
    """Raised when the LLM API key is invalid or expired.

    Common causes:
    - Invalid API key format
    - Expired or revoked key
    - Key doesn't have required permissions
    """

    def __init__(
        self,
        message: str = "Invalid API key",
        provider: str | None = "OpenAI",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, provider, details)


class ModelNotAvailableError(LLMError):
    """Raised when the requested LLM model is not available.

    Common causes:
    - Model name is incorrect
    - Model has been deprecated
    - Model not available in user's region
    """

    def __init__(
        self,
        message: str = "Model not available",
        model: str | None = None,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, provider, details)
        self.model = model


class ContentFilterError(LLMError):
    """Raised when content is filtered by the LLM provider.

    Common causes:
    - Content violates usage policies
    - Prompt contains restricted content
    """

    def __init__(
        self,
        message: str = "Content filtered by provider",
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, provider, details)


# =============================================================================
# Tool Errors - Tool execution related errors
# =============================================================================


class ToolError(GhostfolioAgentError):
    """Base exception for tool-related errors.

    Use when there are issues with tool registration, validation, or execution.
    """

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.tool_name = tool_name


class ToolValidationError(ToolError):
    """Raised when tool input validation fails.

    Common causes:
    - Invalid parameter types
    - Missing required parameters
    - Parameter values out of range
    """

    def __init__(
        self,
        message: str = "Tool validation failed",
        tool_name: str | None = None,
        parameter: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, tool_name, details)
        self.parameter = parameter


class ToolExecutionError(ToolError):
    """Raised when tool execution fails.

    Common causes:
    - External service error during tool execution
    - Unexpected error in tool logic
    - Resource not available
    """

    def __init__(
        self,
        message: str = "Tool execution failed",
        tool_name: str | None = None,
        original_error: Exception | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, tool_name, details)
        self.original_error = original_error


# =============================================================================
# Configuration Errors - Configuration related errors
# =============================================================================


class ConfigurationError(GhostfolioAgentError):
    """Raised when there is a configuration issue.

    Common causes:
    - Missing required environment variables
    - Invalid configuration values
    - Configuration file not found
    """

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.config_key = config_key


# =============================================================================
# Helper functions for error message formatting
# =============================================================================


def get_friendly_error_message(error: Exception) -> str:
    """Convert an exception to a user-friendly message.

    This function provides conversational error messages without
    HTTP/technical jargon for end users.

    Args:
        error: The exception to convert

    Returns:
        A user-friendly error message
    """
    # Handle our custom exceptions first
    if isinstance(error, AuthenticationError):
        service = error.service or "Ghostfolio"
        return (
            f"I can't access your {service} data right now. "
            "Please check your connection settings and try again. "
            f"If using {service}, make sure your access token is valid."
        )

    if isinstance(error, RateLimitError):
        service = error.service or "external service"
        retry_msg = ""
        if error.retry_after:
            retry_msg = f" Please try again in {error.retry_after} seconds."
        return f"I'm hitting rate limits from {service}. Please wait a moment and try again.{retry_msg}"

    if isinstance(error, TimeoutError):
        return "That request took too long and timed out. Please try again in a moment."

    if isinstance(error, ConnectionError):
        service = error.service or "external service"
        return f"I couldn't connect to {service}. Please check your internet connection and try again."

    if isinstance(error, ResourceNotFoundError):
        if error.resource_type:
            return f"I couldn't find the {error.resource_type} you're looking for."
        return "I couldn't find what you're looking for. Please check and try again."

    if isinstance(error, InvalidAPIKeyError):
        return (
            "The AI service API key was rejected (invalid or expired). "
            "Please check the server configuration and update the key."
        )

    if isinstance(error, ModelNotAvailableError):
        model = error.model or "the requested model"
        return f"The AI model '{model}' is not available. Please check the configuration."

    if isinstance(error, ContentFilterError):
        return "Your request couldn't be processed due to content restrictions. Please rephrase and try again."

    if isinstance(error, ToolValidationError):
        return f"There was an issue with the request parameters: {error.message}"

    if isinstance(error, ToolExecutionError):
        return "Something went wrong while processing your request. Please try again."

    if isinstance(error, ConfigurationError):
        return "The server configuration needs attention. Please check the settings."

    if isinstance(error, LLMError):
        return "I'm having trouble with the AI service. Please try again in a moment."

    if isinstance(error, APIError):
        return "Something went wrong communicating with an external service. Please try again."

    if isinstance(error, GhostfolioAgentError):
        return "Something went wrong. Please try again or ask for help."

    # Fallback for non-custom exceptions
    error_str = str(error).lower()

    if "invalid_api_key" in error_str or "incorrect api key" in error_str:
        return (
            "The AI service API key was rejected (invalid or expired). "
            "Please check the server configuration and update the key."
        )

    if "api key" in error_str or "openai" in error_str:
        return (
            "I'm not fully set up yet—the AI service API key isn't configured. "
            "Please check the server configuration and try again."
        )

    if "authentication" in error_str or "access token" in error_str or "401" in error_str:
        return (
            "I can't access your portfolio right now. Please check your "
            "connection settings and try again."
        )

    if "timeout" in error_str or "timed out" in error_str:
        return "That request took too long and timed out. Please try again in a moment."

    if "rate" in error_str and "limit" in error_str:
        return "I'm hitting rate limits from an external service. Please wait a minute and try again."

    # Generic fallback - still conversational
    return (
        "Something went wrong while I was handling that. "
        "You can try rephrasing, or ask me something else."
    )
