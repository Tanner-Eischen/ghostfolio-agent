"""Tools endpoints for Ghostfolio Agent API.

Tool registry, execution, and management.
"""

import time
import uuid

from fastapi import APIRouter, HTTPException

from src.api.models import (
    ToolCreateRequest,
    ToolDetailResponse,
    ToolExecuteRequest,
    ToolExecuteResponse,
    ToolRegistrationRequest,
    ToolRegistrationResponse,
    ToolResponse,
)
from src.tools.code_validator import sanitize_tool_name, validate_generated_tool
from src.tools.registry import (
    get_tool_schema,
    register_generated_tool,
    unregister_generated_tool,
)
from src.tools.registry import (
    list_tools as list_registered_tools,
)
from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/tools", response_model=list[ToolResponse], tags=["Tools"])
async def list_tools() -> list[ToolResponse]:
    """List all available tools.

    Returns descriptions and schemas for all tools the agent can use.
    """
    tools = list_registered_tools()
    return [
        ToolResponse(
            id=tool.get("name", str(uuid.uuid4())),
            name=tool.get("name", "unknown"),
            description=tool.get("description", ""),
            parameters=tool.get("parameters", {}),
            status="active",
        )
        for tool in tools
    ]


@router.get("/tools/{tool_name}", response_model=ToolDetailResponse, tags=["Tools"])
async def get_tool(tool_name: str) -> ToolDetailResponse:
    """Get details for a specific tool.

    Args:
        tool_name: Name of the tool to retrieve

    Returns:
        Tool details including schema and metadata
    """
    tool = get_tool_schema(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return ToolDetailResponse(
        id=tool_name,
        name=tool.get("name", tool_name),
        description=tool.get("description", ""),
        parameters=tool.get("parameters", {}),
        status="active",
        source=tool.get("source", "core"),
        created_at=tool.get("created_at"),
    )


@router.post("/tools/{tool_name}/execute", response_model=ToolExecuteResponse, tags=["Tools"])
async def execute_tool(tool_name: str, request: ToolExecuteRequest) -> ToolExecuteResponse:
    """Execute a tool with given parameters.

    Args:
        tool_name: Name of the tool to execute
        request: Tool execution parameters

    Returns:
        Tool execution result
    """
    tool = get_tool_schema(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    start_time = time.time()

    try:
        # Execute the tool
        from src.tools import ALL_TOOLS

        target_tool = None
        for t in ALL_TOOLS:
            if t.name == tool_name:
                target_tool = t
                break

        if not target_tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found in registry")

        # Execute with provided parameters
        result = await target_tool.ainvoke(request.parameters)

        execution_time = (time.time() - start_time) * 1000

        # Handle Pydantic model results
        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="json")

        return ToolExecuteResponse(
            tool_name=tool_name,
            success=True,
            result=result,
            execution_time_ms=round(execution_time, 2),
        )

    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"Tool execution failed: {e}")

        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            result={"error": str(e)},
            execution_time_ms=round(execution_time, 2),
        )


@router.post("/tools", response_model=ToolResponse, tags=["Tools"])
async def create_tool(request: ToolCreateRequest) -> ToolResponse:
    """Create a new tool (placeholder for future dynamic tool creation).

    Note: In the current implementation, tools are discovered from
    src/tools/ and cannot be created at runtime. This endpoint
    is provided for API compatibility.
    """
    # For now, just return the tool info but don't actually register it
    logger.warning(f"Tool creation requested but not implemented: {request.name}")
    return ToolResponse(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        parameters=request.parameters,
        status="inactive",
    )


@router.post("/tools/register", response_model=ToolRegistrationResponse, tags=["Tools"])
async def register_tool(request: ToolRegistrationRequest) -> ToolRegistrationResponse:
    """Register a generated tool and make it available to the agent.

    This endpoint:
    1. Validates the generated code for safety
    2. Persists the tool to disk
    3. Loads the tool dynamically
    4. Reloads the agent to make the tool available
    """
    from src.agent.core import reload_agent_tools

    logger.info(f"Registering generated tool: {request.name}")

    # Validate the code first
    validation = validate_generated_tool(request.generated_code)

    if not validation.valid:
        error_msg = "; ".join(validation.errors)
        logger.warning(f"Tool validation failed: {error_msg}")
        return ToolRegistrationResponse(
            success=False,
            message=f"Validation failed: {error_msg}",
            tool_name=None,
            warnings=validation.warnings,
        )

    # Sanitize the tool name
    safe_name = sanitize_tool_name(request.name)

    # Register the tool
    success, message = register_generated_tool(
        name=safe_name,
        description=request.description,
        generated_code=request.generated_code,
        source_suggestion_id=request.source_suggestion_id,
        parameters=request.parameters,
    )

    if not success:
        logger.warning(f"Tool registration failed: {message}")
        return ToolRegistrationResponse(
            success=False,
            message=message,
            tool_name=None,
            warnings=validation.warnings,
        )

    # Reload the agent to make the tool available
    reloaded = reload_agent_tools()
    if not reloaded:
        logger.warning("Tool registered but agent reload failed")

    logger.info(f"Tool '{safe_name}' registered successfully, agent reloaded: {reloaded}")

    return ToolRegistrationResponse(
        success=True,
        message=f"Tool '{safe_name}' registered successfully",
        tool_name=safe_name,
        tool_id=safe_name,
        warnings=validation.warnings,
        agent_reloaded=reloaded,
    )


@router.delete("/tools/generated/{tool_name}", response_model=dict, tags=["Tools"])
async def delete_generated_tool(tool_name: str) -> dict:
    """Unregister a generated tool.

    Args:
        tool_name: Name of the generated tool to delete

    Returns:
        Dict with success status
    """
    from src.agent.core import reload_agent_tools

    success, message = unregister_generated_tool(tool_name)
    if not success:
        raise HTTPException(status_code=404, detail=message)

    # Reload agent to reflect changes
    reload_agent_tools()

    return {"status": "deleted", "tool_name": tool_name, "message": message}
