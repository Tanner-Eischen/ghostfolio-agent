"""Per-request context for stateless Ghostfolio token and optional API URL.

The frontend sends X-Ghostfolio-Access-Token and optionally X-Ghostfolio-Api-Url
on each request. Middleware sets them here; GhostfolioClient uses them so each
user's token and instance URL stay private (never stored server-side).

Tokens are instance-specific: a token from local Ghostfolio only works with
that instance's URL. So local/self-hosted users must send their instance URL too.
"""
from contextvars import ContextVar

# Token from current request header; middleware sets this.
REQUEST_GHOSTFOLIO_ACCESS_TOKEN: ContextVar[str | None] = ContextVar(
    "request_ghostfolio_access_token", default=None
)

# Optional API base URL (e.g. http://localhost:3333 for local Ghostfolio).
# When set with a token, client uses this instead of ghostfolio.io.
REQUEST_GHOSTFOLIO_API_URL: ContextVar[str | None] = ContextVar(
    "request_ghostfolio_api_url", default=None
)


def get_request_ghostfolio_token() -> str | None:
    """Return the Ghostfolio access token for the current request, if any."""
    return REQUEST_GHOSTFOLIO_ACCESS_TOKEN.get()


def get_request_ghostfolio_api_url() -> str | None:
    """Return the Ghostfolio API URL for the current request, if any."""
    return REQUEST_GHOSTFOLIO_API_URL.get()
