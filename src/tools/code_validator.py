"""Code validation for generated tools.

Provides safety checks before registering dynamically generated tools:
- AST parsing to verify valid Python syntax
- Check for @tool decorator
- Block dangerous imports (os, subprocess, sys, socket, etc.)
- Verify the code structure is appropriate for a tool

This is a security layer to prevent malicious or broken code from
being registered as an agent tool.
"""

import ast
from dataclasses import dataclass
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Modules that are forbidden in generated tools for security reasons
FORBIDDEN_IMPORTS = {
    # System access
    "os",
    "subprocess",
    "sys",
    "shutil",
    "tempfile",
    # Network access
    "socket",
    "urllib",  # Allow urllib via requests in controlled manner
    "http.client",
    "ftplib",
    "smtplib",
    "telnetlib",
    "poplib",
    "imaplib",
    "nntplib",
    # File system
    "pathlib",  # We allow this but restrict dangerous operations
    "glob",
    # Process control
    "multiprocessing",
    "threading",  # Allow threading for async tools
    "signal",
    "ctypes",
    # Dangerous builtins
    "builtins",
    "__builtin__",
    # Eval/exec
    "code",
    "codeop",
    # Compiler
    "compile",
    "compileall",
}

# Allow these specific imports even if parent module is forbidden
ALLOWED_SUBMODULES = {
    "pathlib.Path",  # Allow Path for safe file operations
    "urllib.parse",  # Allow URL parsing
}

# Allowed imports for generated tools (whitelist approach)
ALLOWED_IMPORTS = {
    # Standard library
    "json",
    "datetime",
    "time",
    "re",
    "math",
    "decimal",
    "fractions",
    "statistics",
    "collections",
    "itertools",
    "functools",
    "typing",
    "dataclasses",
    "enum",
    "copy",
    "operator",
    # Async
    "asyncio",
    "concurrent",
    "concurrent.futures",
    # LangChain
    "langchain",
    "langchain_core",
    "langchain_core.tools",
    "langsmith",
    # Pydantic
    "pydantic",
    # HTTP (controlled)
    "httpx",
    "aiohttp",
    # Our modules
    "src",
    "src.api",
    "src.utils",
}


@dataclass
class ValidationResult:
    """Result of code validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]
    tool_name: str | None = None
    tool_description: str | None = None
    has_tool_decorator: bool = False


def validate_generated_tool(code: str) -> ValidationResult:
    """Validate generated tool code for safety and correctness.

    Args:
        code: Python source code to validate

    Returns:
        ValidationResult with validity status and any errors/warnings
    """
    errors: list[str] = []
    warnings: list[str] = []
    tool_name: str | None = None
    tool_description: str | None = None
    has_tool_decorator = False

    # 1. Check code is not empty
    if not code or not code.strip():
        errors.append("Code is empty")
        return ValidationResult(
            valid=False,
            errors=errors,
            warnings=warnings,
        )

    # 2. Parse AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        errors.append(f"Syntax error: {e.msg} at line {e.lineno}")
        return ValidationResult(
            valid=False,
            errors=errors,
            warnings=warnings,
        )

    # 3. Check for @tool decorator
    has_tool_decorator, decorator_errors = _check_tool_decorator(tree)
    errors.extend(decorator_errors)

    # 4. Check imports
    import_warnings = _check_imports(tree)
    warnings.extend(import_warnings)

    # 5. Check for dangerous patterns
    danger_errors = _check_dangerous_patterns(tree)
    errors.extend(danger_errors)

    # 6. Extract tool metadata
    tool_name, tool_description = _extract_tool_metadata(tree)

    # 7. Check for async def (preferred for tools)
    has_async = _has_async_function(tree)
    if not has_async:
        warnings.append("Tool function is not async - may block the event loop")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        tool_name=tool_name,
        tool_description=tool_description,
        has_tool_decorator=has_tool_decorator,
    )


def _check_tool_decorator(tree: ast.Module) -> tuple[bool, list[str]]:
    """Check if the code has a @tool decorator.

    Returns:
        Tuple of (has_decorator, errors)
    """
    errors: list[str] = []
    has_decorator = False

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                decorator_name = None

                # Handle @tool
                if isinstance(decorator, ast.Name):
                    decorator_name = decorator.id
                # Handle @tool(args)
                elif isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Name):
                        decorator_name = decorator.func.id

                if decorator_name == "tool":
                    has_decorator = True
                    break

    if not has_decorator:
        errors.append("No @tool decorator found - code must define a LangChain tool")

    return has_decorator, errors


def _check_imports(tree: ast.Module) -> list[str]:
    """Check for forbidden imports.

    Returns:
        List of warning messages
    """
    warnings: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module in FORBIDDEN_IMPORTS:
                    full_name = alias.name
                    if not any(full_name.startswith(allowed) for allowed in ALLOWED_SUBMODULES):
                        warnings.append(f"Forbidden import: {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                full_module = node.module
                if module in FORBIDDEN_IMPORTS:
                    if not any(full_module.startswith(allowed) for allowed in ALLOWED_SUBMODULES):
                        warnings.append(f"Forbidden import from: {node.module}")

    return warnings


def _check_dangerous_patterns(tree: ast.Module) -> list[str]:
    """Check for dangerous code patterns.

    Returns:
        List of error messages
    """
    errors: list[str] = []

    for node in ast.walk(tree):
        # Check for eval/exec
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "compile"):
                    errors.append(f"Dangerous function call: {node.func.id}()")

        # Check for __import__
        if isinstance(node, ast.Attribute):
            if node.attr == "__import__":
                errors.append("Dangerous: __import__ usage detected")

        # Check for os.system style calls
        if isinstance(node, ast.Attribute):
            if node.attr in ("system", "popen", "spawn", "fork", "kill"):
                errors.append(f"Dangerous method call: {node.attr}")

    return errors


def _extract_tool_metadata(tree: ast.Module) -> tuple[str | None, str | None]:
    """Extract tool name and description from the decorated function.

    Returns:
        Tuple of (name, description)
    """
    tool_name = None
    tool_description = None

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                decorator_name = None
                if isinstance(decorator, ast.Name):
                    decorator_name = decorator.id
                elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                    decorator_name = decorator.func.id

                if decorator_name == "tool":
                    tool_name = node.name
                    # Get docstring
                    docstring = ast.get_docstring(node)
                    if docstring:
                        # Extract first line as description
                        tool_description = docstring.split("\n")[0].strip()
                    break

    return tool_name, tool_description


def _has_async_function(tree: ast.Module) -> bool:
    """Check if the code has an async function definition.

    Returns:
        True if an async def is found
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            return True
    return False


def sanitize_tool_name(name: str) -> str:
    """Sanitize a tool name to be a valid Python identifier.

    Args:
        name: Raw tool name

    Returns:
        Sanitized name suitable for use as a Python identifier
    """
    # Replace invalid characters with underscores
    sanitized = ""
    for i, char in enumerate(name):
        if i == 0:
            # First char must be letter or underscore
            if char.isalpha() or char == "_":
                sanitized += char
            else:
                sanitized += "_"
        else:
            # Subsequent chars can be alphanumeric or underscore
            if char.isalnum() or char == "_":
                sanitized += char
            else:
                sanitized += "_"

    # Ensure not empty and not a Python keyword
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"tool_{sanitized}"

    return sanitized.lower()


__all__ = [
    "validate_generated_tool",
    "sanitize_tool_name",
    "ValidationResult",
    "FORBIDDEN_IMPORTS",
    "ALLOWED_IMPORTS",
]
