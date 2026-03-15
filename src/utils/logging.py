"""Logging configuration and utilities."""

import logging
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

from src.utils.config import get_settings

console = Console()


def setup_logging() -> None:
    """Configure logging with Rich handler."""
    settings = get_settings()

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                show_time=True,
                show_path=settings.is_development,
                rich_tracebacks=True,
                tracebacks_show_locals=settings.is_development,
            )
        ],
    )

    # Set third-party loggers to WARNING
    for logger_name in ["httpx", "httpcore", "urllib3"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter for adding context."""

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Add extra context to log messages."""
        extra = kwargs.get("extra", {})
        extra.update(self.extra or {})
        kwargs["extra"] = extra
        return msg, kwargs
