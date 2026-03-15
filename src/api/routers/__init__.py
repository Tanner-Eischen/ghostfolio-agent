"""Routers for Ghostfolio Agent API.

This package contains modular routers organized by domain:
- system: Health, metrics, root endpoints
- chat: Chat endpoint
- sessions: Session management
- feedback: Feedback submission
- portfolio: Portfolio summary, risk assessment
- market: Market data lookup
- strategy: Strategy configuration
- tools: Tool registry and execution
- verification: Verification configuration
- traces: LangSmith traces
- evals: Evaluation endpoints
- finances: Usage stats and cost projections
"""

from src.api.routers.agent import router as agent_router
from src.api.routers.chat import router as chat_router
from src.api.routers.evals import router as evals_router
from src.api.routers.feedback import router as feedback_router
from src.api.routers.finances import router as finances_router
from src.api.routers.market import router as market_router
from src.api.routers.portfolio import router as portfolio_router
from src.api.routers.sessions import router as sessions_router
from src.api.routers.strategy import router as strategy_router
from src.api.routers.system import router as system_router
from src.api.routers.tools import router as tools_router
from src.api.routers.traces import router as traces_router
from src.api.routers.verification import router as verification_router

__all__ = [
    "system_router",
    "chat_router",
    "sessions_router",
    "feedback_router",
    "portfolio_router",
    "market_router",
    "strategy_router",
    "tools_router",
    "verification_router",
    "traces_router",
    "evals_router",
    "finances_router",
    "agent_router",
]
