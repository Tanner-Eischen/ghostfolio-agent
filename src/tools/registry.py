"""Dynamic tool registry for Ghostfolio Agent tools.

Provides functions to discover and list available tools from the
src/tools/ directory, including both core tools and dynamically
generated tools.

This module auto-discovers tools based on the CORE_TOOLS list in
src/tools/__init__.py and loads generated tools from disk,
extracting schemas and descriptions.
"""

import importlib.util
import sys
from typing import Any

from langchain_core.tools import BaseTool

from src.tools.code_validator import validate_generated_tool
from src.tools.generated_store import GeneratedToolEntry, get_generated_tool_store
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Cache for loaded generated tools
_generated_tools_cache: dict[str, BaseTool] = {}


def _get_core_tools() -> list[BaseTool]:
    """Get core tools lazily to avoid circular imports."""
    from src.tools import CORE_TOOLS

    return CORE_TOOLS


def list_tools() -> list[dict[str, Any]]:
    """List all available tools (core + generated).

    Returns:
        List of tool dictionaries with id, name, description, parameters, status
    """
    tools = []

    # Add core tools
    for tool in _get_core_tools():
        tool_info = {
            "id": tool.name,
            "name": tool.name,
            "description": tool.description,
            "parameters": _extract_parameters(tool),
            "status": "active",
            "source": "core",
        }
        tools.append(tool_info)

    # Add generated tools
    for tool in load_generated_tools():
        tool_info = {
            "id": tool.name,
            "name": tool.name,
            "description": tool.description,
            "parameters": _extract_parameters(tool),
            "status": "active",
            "source": "generated",
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
    all_tools = get_all_tools()
    for tool in all_tools:
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
    all_tools = get_all_tools()
    for tool in all_tools:
        if tool.name == tool_name:
            return tool
    return None


def get_all_tools() -> list[BaseTool]:
    """Get all tools (core + generated).

    Returns:
        List of all tool instances
    """
    return _get_core_tools() + load_generated_tools()


def load_generated_tools() -> list[BaseTool]:
    """Load all generated tools from disk.

    Returns:
        List of generated tool instances
    """
    global _generated_tools_cache

    tools: list[BaseTool] = []
    store = get_generated_tool_store()

    for entry in store.list_generated_tools():
        tool = _load_tool_from_entry(entry)
        if tool:
            tools.append(tool)

    return tools


def _load_tool_from_entry(entry: GeneratedToolEntry) -> BaseTool | None:
    """Load a tool from a GeneratedToolEntry.

    Args:
        entry: The tool entry to load

    Returns:
        BaseTool instance or None if loading fails
    """
    global _generated_tools_cache

    # Check cache first
    if entry.name in _generated_tools_cache:
        return _generated_tools_cache[entry.name]

    try:
        # Create a module from the code
        module_name = f"generated_tool_{entry.name}"
        spec = importlib.util.spec_from_loader(module_name, loader=None)
        if spec is None or spec.loader is None:
            logger.error(f"Failed to create module spec for tool {entry.name}")
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        # Execute the code in the module
        exec(entry.generated_code, module.__dict__)

        # Find the tool function (decorated with @tool)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, BaseTool):
                _generated_tools_cache[entry.name] = attr
                logger.info(f"Loaded generated tool: {entry.name}")
                return attr

        logger.warning(f"No @tool decorator found in generated tool {entry.name}")
        return None

    except Exception as e:
        logger.error(f"Failed to load generated tool {entry.name}: {e}")
        return None


def register_generated_tool(
    name: str,
    description: str,
    generated_code: str,
    source_suggestion_id: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Register a new generated tool.

    Args:
        name: Tool name (must be unique)
        description: Tool description
        generated_code: Full Python source code with @tool decorator
        source_suggestion_id: Optional ID of the suggestion that generated this tool
        parameters: Optional parameter schema

    Returns:
        Tuple of (success, message)
    """
    # Validate the code first
    validation = validate_generated_tool(generated_code)
    if not validation.valid:
        error_msg = "; ".join(validation.errors)
        return False, f"Validation failed: {error_msg}"

    # Use extracted name from code if not provided
    actual_name = validation.tool_name or name

    # Store the tool
    store = get_generated_tool_store()
    try:
        entry = store.register_tool(
            name=actual_name,
            description=description or validation.tool_description or "",
            generated_code=generated_code,
            source_suggestion_id=source_suggestion_id,
            parameters=parameters,
        )
    except ValueError as e:
        return False, str(e)

    # Clear cache to force reload
    clear_tool_cache()

    # Load the tool to verify it works
    tool = _load_tool_from_entry(entry)
    if tool is None:
        store.unregister_tool(actual_name)
        return False, "Failed to load tool after registration"

    return True, f"Tool '{actual_name}' registered successfully"


def unregister_generated_tool(name: str) -> tuple[bool, str]:
    """Unregister a generated tool.

    Args:
        name: Tool name to unregister

    Returns:
        Tuple of (success, message)
    """
    global _generated_tools_cache

    store = get_generated_tool_store()

    # Check if it's a generated tool
    if not store.tool_exists(name):
        return False, f"Generated tool '{name}' not found"

    # Remove from cache
    if name in _generated_tools_cache:
        del _generated_tools_cache[name]

    # Remove from store
    success = store.unregister_tool(name)

    if success:
        return True, f"Tool '{name}' unregistered successfully"
    else:
        return False, f"Failed to unregister tool '{name}'"


def clear_tool_cache() -> None:
    """Clear the generated tools cache."""
    global _generated_tools_cache
    _generated_tools_cache = {}
    logger.info("Cleared generated tools cache")


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
    """Get the number of registered tools (core + generated).

    Returns:
        Number of tools
    """
    return len(_get_core_tools()) + get_generated_tool_store().get_tool_count()


__all__ = [
    "list_tools",
    "get_tool_schema",
    "get_tool_by_name",
    "get_tool_count",
    "get_all_tools",
    "load_generated_tools",
    "register_generated_tool",
    "unregister_generated_tool",
    "clear_tool_cache",
]
