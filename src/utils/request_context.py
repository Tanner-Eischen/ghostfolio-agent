"""Per-request context for stateless Ghostfolio token.

The frontend sends X-Ghostfolio-Access-Token on each request. Middleware
sets it here; GhostfolioClient uses it so each user's token stays private
(never stored server-side).
"""
from contextvars import ContextVar

# Token from current request header; middleware sets this.
REQUEST_GHOSTFOLIO_ACCESS_TOKEN: ContextVar[str | None] = ContextVar(
    "request_ghostfolio_access_token", default=None
)


def get_request_ghostfolio_token() -> str | None:
    """Return the Ghostfolio access token for the current request, if any."""
    return REQUEST_GHOSTFOLIO_ACCESS_TOKEN.get()
