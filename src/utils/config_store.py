"""Persistent JSON configuration storage.

Provides a simple JSON-file backed configuration store that persists
settings across application restarts.

Used by:
- Verification pipeline configuration
- Strategy configuration
- Other runtime settings
"""

import json
import os
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


def _get_config_dir() -> Path:
    """Get config directory, creating it if possible."""
    # Check for environment variable first (for production)
    config_dir_env = os.environ.get("DATA_DIR", os.environ.get("RAILWAY_DATA_DIR"))
    if config_dir_env:
        config_dir = Path(config_dir_env)
    else:
        # Default to ./data relative to project root
        config_dir = Path(__file__).parent.parent.parent / "data"

    # Try to create the directory, fall back to /tmp if permission denied
    try:
        config_dir.mkdir(exist_ok=True, parents=True)
        return config_dir
    except PermissionError:
        # In production containers, fall back to /tmp
        fallback = Path("/tmp/ghostfolio-agent-data")
        fallback.mkdir(exist_ok=True, parents=True)
        logger.warning(f"Could not create {config_dir}, using fallback: {fallback}")
        return fallback


# Default config directory
CONFIG_DIR = _get_config_dir()


class ConfigStore:
    """JSON-file backed configuration store.

    Provides atomic read/write access to a JSON configuration file.
    Thread-safe for basic use cases (read-modify-write pattern).

    Example:
        store = ConfigStore("verification.json")
        store.set("confidence_threshold", 70)
        threshold = store.get("confidence_threshold", default=70)
    """

    def __init__(self, filename: str, defaults: dict[str, Any] | None = None):
        """Initialize config store.

        Args:
            filename: Name of the JSON file (stored in data/ directory)
            defaults: Default values if file doesn't exist
        """
        self.filepath = CONFIG_DIR / filename
        self.defaults = defaults or {}
        self._cache: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        """Load config from file."""
        if self._cache is not None:
            return self._cache

        if not self.filepath.exists():
            # Create with defaults
            data = dict(self.defaults)
            self._save(data)
            self._cache = data
            return data

        try:
            with open(self.filepath) as f:
                data = json.load(f)
            self._cache = data
            return data
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Config file corrupted, resetting: {e}")
            data = dict(self.defaults)
            self._save(data)
            self._cache = data
            return data

    def _save(self, data: dict[str, Any]) -> None:
        """Save config to file."""
        with open(self.filepath, "w") as f:
            json.dump(data, f, indent=2)
        self._cache = data

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value.

        Args:
            key: Config key (supports dot notation for nested keys)
            default: Default value if key not found

        Returns:
            Config value or default
        """
        data = self._load()

        # Support dot notation for nested keys
        keys = key.split(".")
        value = data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a config value.

        Args:
            key: Config key (supports dot notation for nested keys)
            value: Value to set
        """
        data = self._load()

        # Support dot notation for nested keys
        keys = key.split(".")
        target = data
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

        self._save(data)
        logger.debug(f"Config updated: {key} = {value}")

    def get_all(self) -> dict[str, Any]:
        """Get all config values.

        Returns:
            Complete config dictionary
        """
        return dict(self._load())

    def update(self, updates: dict[str, Any]) -> None:
        """Update multiple config values at once.

        Args:
            updates: Dictionary of key-value pairs to update
        """
        data = self._load()
        data.update(updates)
        self._save(data)
        logger.debug(f"Config updated with {len(updates)} values")

    def reset(self) -> None:
        """Reset config to defaults."""
        self._save(dict(self.defaults))
        logger.info("Config reset to defaults")


# Pre-configured stores for common use cases

# Verification configuration defaults
VERIFICATION_DEFAULTS = {
    "fact_checking": True,
    "hallucination_detection": True,
    "confidence_scoring": True,
    "hitl_enabled": False,
    "confidence_threshold": 70,
    "strict_mode": False,
}

# Strategy configuration defaults
STRATEGY_DEFAULTS = {
    "framework": "LangGraph",
    "model": "GPT-4o (OpenAI)",
    "temperature": 0.0,
    "json_mode": True,
    "stream_responses": False,
    "contribution_path": "langchain",
}

# Agent configuration defaults (LLM model for chat)
AGENT_DEFAULTS = {
    "model": "gpt-4o-mini",
}


def get_verification_config_store() -> ConfigStore:
    """Get the verification config store."""
    return ConfigStore("verification_config.json", VERIFICATION_DEFAULTS)


def get_strategy_config_store() -> ConfigStore:
    """Get the strategy config store."""
    return ConfigStore("strategy_config.json", STRATEGY_DEFAULTS)


def get_agent_config_store() -> ConfigStore:
    """Get the agent config store (model selection, etc.)."""
    return ConfigStore("agent_config.json", AGENT_DEFAULTS)


__all__ = [
    "ConfigStore",
    "get_verification_config_store",
    "get_strategy_config_store",
    "get_agent_config_store",
    "VERIFICATION_DEFAULTS",
    "STRATEGY_DEFAULTS",
    "AGENT_DEFAULTS",
]
