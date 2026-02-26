"""Dynamic tool registry for Ghostfolio Agent tools.

Provides functions to discover and list available tools from the
src/tools/ directory.

This module auto-discovers tools based on the ALL_TOOLS list in
src/tools/__init__.py, extracting schemas and descriptions.
"""

from typing import Any

from src.tools import ALL_TOOLS
from src.utils.logging import get_logger

logger = get_logger(__name__)


def list_tools() -> list[dict[str, Any]]:
    """List all available tools.

    Returns:
        List of tool dictionaries with id, name, description, parameters, status
    """
    tools = []

    for tool in ALL_TOOLS:
        # Extract tool info
        tool_info = {
            "id": tool.name,
            "name": tool.name,
            "description": tool.description,
            "parameters": _extract_parameters(tool),
            "status": "active",
        }
        tools.append(tool_info)

    return tools


def get_tool_schema(tool_name: str) -> dict[str, Any] | None:
    """Get the schema for a specific tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Tool schema dictionary or None if not found
    """
    for tool in ALL_TOOLS:
        if tool.name == tool_name:
            return {
                "name": tool.name,
                "description": tool.description,
                "parameters": _extract_parameters(tool),
                "args_schema": _get_args_schema(tool),
            }
    return None


def get_tool_by_name(tool_name: str) -> Any | None:
    """Get a tool instance by name.

    Args:
        tool_name: Name of the tool

    Returns:
        Tool instance or None if not found
    """
    for tool in ALL_TOOLS:
        if tool.name == tool_name:
            return tool
    return None


def _extract_parameters(tool: Any) -> dict[str, Any]:
    """Extract parameter info from a tool.

    Args:
        tool: LangChain tool instance

    Returns:
        Dictionary of parameter name -> type description
    """
    parameters = {}

    # Try to get from args_schema
    if hasattr(tool, "args_schema") and tool.args_schema:
        schema = tool.args_schema.schema()
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for name, prop in properties.items():
            param_type = prop.get("type", "any")
            if "enum" in prop:
                param_type = f"enum[{', '.join(prop['enum'])}]"
            elif prop.get("format") == "date-time":
                param_type = "datetime"
            elif "items" in prop:
                item_type = prop["items"].get("type", "any")
                param_type = f"array<{item_type}>"

            parameters[name] = {
                "type": param_type,
                "description": prop.get("description", ""),
                "required": name in required,
            }

    # Fallback to tool.args if available
    elif hasattr(tool, "args"):
        for arg in tool.args:
            parameters[arg] = {"type": "any", "required": True}

    return parameters


def _get_args_schema(tool: Any) -> dict[str, Any] | None:
    """Get the full args schema for a tool.

    Args:
        tool: LangChain tool instance

    Returns:
        JSON schema dict or None
    """
    if hasattr(tool, "args_schema") and tool.args_schema:
        return tool.args_schema.schema()
    return None


def get_tool_count() -> int:
    """Get the number of registered tools.

    Returns:
        Number of tools
    """
    return len(ALL_TOOLS)


__all__ = [
    "list_tools",
    "get_tool_schema",
    "get_tool_by_name",
    "get_tool_count",
]
