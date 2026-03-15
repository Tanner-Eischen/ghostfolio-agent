"""Persistent storage for dynamically generated tools.

Stores generated tool code and metadata to disk, enabling tools to persist
across server restarts. Follows the same pattern as FeedbackStore.

Storage structure:
    data/generated_tools/registry.json   # Tool metadata
    data/generated_tools/{tool_name}.py  # Tool source code

Each tool entry contains:
- name: Tool name (unique identifier)
- description: Tool description
- generated_code: Full Python source code
- source_suggestion_id: ID of the suggestion that generated this tool
- parameters: Parameter schema
- created_at: Registration timestamp
"""

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Storage paths
GENERATED_TOOLS_DIR = Path(__file__).parent.parent.parent / "data" / "generated_tools"
REGISTRY_FILE = GENERATED_TOOLS_DIR / "registry.json"


@dataclass
class GeneratedToolEntry:
    """Metadata for a generated tool."""

    name: str
    description: str
    generated_code: str
    source_suggestion_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    file_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeneratedToolEntry":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            generated_code=data.get("generated_code", ""),
            source_suggestion_id=data.get("source_suggestion_id"),
            parameters=data.get("parameters", {}),
            created_at=data.get("created_at", ""),
            file_path=data.get("file_path", ""),
        )


class GeneratedToolStore:
    """Thread-safe storage for generated tools."""

    def __init__(self, storage_dir: Path | None = None):
        """Initialize the generated tool store.

        Args:
            storage_dir: Optional custom storage directory (for testing)
        """
        self.storage_dir = storage_dir or GENERATED_TOOLS_DIR
        self.registry_file = self.storage_dir / "registry.json"
        self._lock = threading.Lock()
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        """Ensure the storage directory and registry file exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        if not self.registry_file.exists():
            self._write_registry({})

    def _read_registry(self) -> dict[str, dict[str, Any]]:
        """Read the tool registry from disk."""
        try:
            with open(self.registry_file, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_registry(self, registry: dict[str, dict[str, Any]]) -> None:
        """Write the tool registry to disk."""
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)

    def _get_tool_file_path(self, tool_name: str) -> Path:
        """Get the file path for a tool's source code."""
        # Sanitize tool name for filesystem
        safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in tool_name)
        return self.storage_dir / f"{safe_name}.py"

    def register_tool(
        self,
        name: str,
        description: str,
        generated_code: str,
        source_suggestion_id: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> GeneratedToolEntry:
        """Register a new generated tool.

        Args:
            name: Tool name (must be unique)
            description: Tool description
            generated_code: Full Python source code with @tool decorator
            source_suggestion_id: Optional ID of the suggestion that generated this tool
            parameters: Optional parameter schema

        Returns:
            The created GeneratedToolEntry

        Raises:
            ValueError: If a tool with the same name already exists
        """
        with self._lock:
            registry = self._read_registry()

            # Check for duplicate
            if name in registry:
                raise ValueError(f"Tool '{name}' already exists")

            # Create entry
            now = datetime.now(timezone.utc)
            file_path = self._get_tool_file_path(name)

            entry = GeneratedToolEntry(
                name=name,
                description=description,
                generated_code=generated_code,
                source_suggestion_id=source_suggestion_id,
                parameters=parameters or {},
                created_at=now.isoformat(),
                file_path=str(file_path),
            )

            # Save tool code to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(generated_code)

            # Update registry
            registry[name] = entry.to_dict()
            self._write_registry(registry)

            logger.info(f"Registered generated tool '{name}' at {file_path}")
            return entry

    def unregister_tool(self, name: str) -> bool:
        """Unregister a generated tool.

        Args:
            name: Tool name to unregister

        Returns:
            True if tool was removed, False if not found
        """
        with self._lock:
            registry = self._read_registry()

            if name not in registry:
                return False

            entry_data = registry[name]
            file_path = Path(entry_data.get("file_path", ""))

            # Remove from registry
            del registry[name]
            self._write_registry(registry)

            # Remove source file
            if file_path.exists():
                file_path.unlink()

            logger.info(f"Unregistered generated tool '{name}'")
            return True

    def get_tool(self, name: str) -> GeneratedToolEntry | None:
        """Get a generated tool by name.

        Args:
            name: Tool name

        Returns:
            GeneratedToolEntry or None if not found
        """
        registry = self._read_registry()
        if name in registry:
            return GeneratedToolEntry.from_dict(registry[name])
        return None

    def list_generated_tools(self) -> list[GeneratedToolEntry]:
        """List all generated tools.

        Returns:
            List of GeneratedToolEntry objects
        """
        registry = self._read_registry()
        return [GeneratedToolEntry.from_dict(data) for data in registry.values()]

    def load_tool_code(self, name: str) -> str | None:
        """Load the source code for a generated tool.

        Args:
            name: Tool name

        Returns:
            Source code string or None if not found
        """
        entry = self.get_tool(name)
        if entry:
            return entry.generated_code
        return None

    def tool_exists(self, name: str) -> bool:
        """Check if a tool with the given name exists.

        Args:
            name: Tool name

        Returns:
            True if tool exists, False otherwise
        """
        registry = self._read_registry()
        return name in registry

    def get_tool_count(self) -> int:
        """Get the number of registered generated tools.

        Returns:
            Number of generated tools
        """
        return len(self._read_registry())

    def clear_all(self) -> None:
        """Clear all generated tools (for testing)."""
        with self._lock:
            registry = self._read_registry()
            # Remove all source files
            for entry_data in registry.values():
                file_path = Path(entry_data.get("file_path", ""))
                if file_path.exists():
                    file_path.unlink()
            # Clear registry
            self._write_registry({})


# Singleton instance
_store_instance: GeneratedToolStore | None = None


def get_generated_tool_store() -> GeneratedToolStore:
    """Get the singleton GeneratedToolStore instance."""
    global _store_instance
    if _store_instance is None:
        _store_instance = GeneratedToolStore()
    return _store_instance


__all__ = [
    "GeneratedToolStore",
    "GeneratedToolEntry",
    "get_generated_tool_store",
]
