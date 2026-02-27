"""Repository connection manager for docking workbench.

This module manages connections to target repositories (git or local) for analysis.
Provides secure cloning, path validation, and connection lifecycle management.
"""

import asyncio
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from src.utils.logging import get_logger

logger = get_logger(__name__)


def _get_repos_dir() -> Path:
    """Get repos directory, creating it if possible."""
    # Check for environment variable first (for production)
    data_dir_env = os.environ.get("DATA_DIR", os.environ.get("RAILWAY_DATA_DIR"))
    if data_dir_env:
        return Path(data_dir_env) / "repos"
    else:
        return Path("data/repos")


# Configuration
REPOS_DIR = _get_repos_dir()
CLONE_TIMEOUT_SECONDS = 60

# Security: Blocked protocols and patterns
BLOCKED_PROTOCOLS = {"file", "ftp", "sftp", "ssh"}
# Note: Removed C:\Users to allow connecting local project directories
# Path traversal and other checks still protect against misuse
SENSITIVE_PATHS = {
    "/etc", "/root", "/home", "/var", "/usr", "/bin", "/sbin",
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
}

# Path traversal patterns to block
PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",           # ../
    r"\.\.\\",          # ..\
    r"\.\.$",           # ends with ..
    r"^/etc/",          # etc directory
    r"^/root/",         # root home
]


class RepoConnectionRequest(BaseModel):
    """Request to connect to a repository."""
    source: str = Field(..., description="Git URL or local path to the repository")
    branch: Optional[str] = Field(default=None, description="Branch to checkout (default: main/master)")
    name: Optional[str] = Field(default=None, description="Optional name for the connection")


class RepoConnection(BaseModel):
    """Information about a connected repository."""
    id: str = Field(..., description="Unique connection ID")
    name: str = Field(..., description="Repository name")
    source: str = Field(..., description="Original source URL or path")
    branch: Optional[str] = Field(default=None, description="Branch name")
    path: str = Field(..., description="Local path to the repository")
    connected_at: str = Field(..., description="ISO timestamp of connection")
    is_local: bool = Field(default=False, description="Whether this is a local path (not cloned)")


class RepoConnectionResponse(BaseModel):
    """Response after connecting to a repository."""
    success: bool = Field(..., description="Whether connection was successful")
    connection: Optional[RepoConnection] = Field(default=None, description="Connection details if successful")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class RepoManager:
    """Manages repository connections for the docking workbench.

    Handles:
    - Git repository cloning with timeout
    - Local path validation and registration
    - Connection lifecycle (connect, disconnect, list)
    - Security: protocol blocking, path traversal protection
    """

    def __init__(self, repos_dir: Path | None = None):
        if repos_dir is None:
            repos_dir = REPOS_DIR
        self.repos_dir = repos_dir

        # Try to create the directory, fall back to /tmp if permission denied
        try:
            self.repos_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            fallback = Path("/tmp/ghostfolio-agent-repos")
            fallback.mkdir(parents=True, exist_ok=True)
            self.repos_dir = fallback
            logger.warning(f"Could not create {repos_dir}, using fallback: {fallback}")

        self._connections: dict[str, RepoConnection] = {}

    def _validate_source(self, source: str) -> tuple[bool, str, Optional[str]]:
        """Validate the source URL or path.

        Returns:
            Tuple of (is_valid, error_message, source_type)
            source_type is 'git', 'local', or None if invalid
        """
        source = source.strip()

        if not source:
            return False, "Source cannot be empty", None

        # Check for git URLs
        git_patterns = [
            r"^https?://",           # http:// or https://
            r"^git://",              # git://
            r"^git@",                # git@host:path
            r"^ssh://",              # ssh://
        ]

        is_git = any(re.match(pattern, source) for pattern in git_patterns)

        if is_git:
            # Block dangerous protocols
            parsed = urlparse(source)
            if parsed.scheme.lower() in BLOCKED_PROTOCOLS:
                return False, f"Protocol '{parsed.scheme}' is not allowed", None

            # Block embedded credentials
            if "@" in source and "://" in source:
                # Check if it's credentials in URL (not git@)
                if not source.startswith("git@"):
                    match = re.search(r"://[^:]+:[^@]+@", source)
                    if match:
                        return False, "Embedded credentials in URLs are not allowed", None

            return True, "", "git"

        # Block URLs with blocked schemes (e.g. file://) before treating as local path
        parsed = urlparse(source)
        if parsed.scheme and parsed.scheme.lower() in BLOCKED_PROTOCOLS:
            return False, f"Protocol '{parsed.scheme}' is not allowed", None

        # Treat as local path
        return self._validate_local_path(source)

    def _validate_local_path(self, path: str) -> tuple[bool, str, Optional[str]]:
        """Validate a local filesystem path.

        Security checks:
        - Path traversal prevention
        - Sensitive directory blocking
        - Path existence and accessibility
        """
        path = path.strip()

        # Normalize path
        try:
            resolved = Path(path).resolve()
        except Exception as e:
            return False, f"Invalid path format: {e}", None

        path_str = str(resolved)

        # Check for path traversal patterns
        for pattern in PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, path_str, re.IGNORECASE):
                return False, "Path traversal detected - access denied", None

        # Block sensitive paths (case-insensitive on Windows)
        for sensitive in SENSITIVE_PATHS:
            if path_str.lower().startswith(sensitive.lower()):
                return False, f"Access to system directories is not allowed", None

        # Check path exists and is a directory (path is resolved on the server)
        if not resolved.exists():
            return False, (
                "That path does not exist on this machine. "
                "Local paths are checked where the backend runs—use a path that exists there, or connect with a Git URL instead (e.g. https://github.com/user/repo.git)."
            ), None

        if not resolved.is_dir():
            return False, f"Path is not a directory: {path}", None

        return True, "", "local"

    def _extract_repo_name(self, source: str) -> str:
        """Extract a repository name from URL or path."""
        source = source.strip().rstrip("/")

        # Remove .git suffix
        if source.endswith(".git"):
            source = source[:-4]

        # Get last segment
        name = source.split("/")[-1]

        # Handle git@ URLs
        if ":" in name and "@" in source:
            name = name.split(":")[-1].replace("/", "-")

        # Handle Windows paths
        if "\\" in name:
            name = name.split("\\")[-1]

        # Fallback
        if not name or name == ".":
            name = "unknown-repo"

        return name

    async def connect(self, request: RepoConnectionRequest) -> RepoConnectionResponse:
        """Connect to a repository.

        For git URLs: clones the repository
        For local paths: validates and registers the path

        Args:
            request: Connection request with source, optional branch, optional name

        Returns:
            RepoConnectionResponse with connection details or error
        """
        is_valid, error, source_type = self._validate_source(request.source)

        if not is_valid:
            return RepoConnectionResponse(success=False, error=error)

        repo_id = str(uuid.uuid4())[:8]
        name = request.name or self._extract_repo_name(request.source)
        now = datetime.utcnow().isoformat()

        if source_type == "git":
            # Check Git is available before attempting clone (avoids opaque failures on Windows)
            git_ok, git_error = await self._check_git_available()
            if not git_ok:
                return RepoConnectionResponse(success=False, error=git_error)

            clone_path = self.repos_dir / repo_id

            try:
                await self._clone_repo(request.source, clone_path, request.branch)
            except FileNotFoundError:
                return RepoConnectionResponse(
                    success=False,
                    error="Git is not installed or not in PATH. Install Git to clone repositories."
                )
            except RuntimeError as e:
                msg = (str(e) or "").strip()
                if not msg:
                    msg = "Clone failed. Check the URL and network, and ensure Git is installed where the backend runs."
                return RepoConnectionResponse(success=False, error=msg)
            except Exception as e:
                logger.exception("Failed to clone repository: %s", e)
                return RepoConnectionResponse(
                    success=False,
                    error="Clone failed. Try a public Git URL (e.g. https://github.com/ghostfolio/ghostfolio.git). If that also fails, ensure Git is installed where the backend runs and check server logs."
                )

            connection = RepoConnection(
                id=repo_id,
                name=name,
                source=request.source,
                branch=request.branch,
                path=str(clone_path),
                connected_at=now,
                is_local=False,
            )

        else:  # local
            resolved_path = str(Path(request.source).resolve())
            connection = RepoConnection(
                id=repo_id,
                name=name,
                source=request.source,
                branch=request.branch,
                path=resolved_path,
                connected_at=now,
                is_local=True,
            )

        self._connections[repo_id] = connection
        logger.info(f"Connected to repository: {name} (id={repo_id})")

        return RepoConnectionResponse(success=True, connection=connection)

    def _normalize_clone_error(self, raw: str) -> str:
        """Turn git clone stderr into a short, user-safe message."""
        if not raw or not raw.strip():
            return "Clone failed. Check the URL and network, and ensure Git is installed."
        msg = raw.strip()
        # Decode / truncate for safety and readability
        if len(msg) > 400:
            msg = msg[:400] + "..."
        # One line for UI
        msg = " ".join(msg.splitlines()).strip()
        lower = msg.lower()
        if "not recognized" in lower or "command not found" in lower or "not found" in lower and "git" in lower:
            return "Git is not installed or not in PATH. Install Git and ensure it is available in your shell."
        if "could not read username" in lower or "authentication failed" in lower or "support for password authentication was removed" in lower:
            return "Authentication failed. Use a personal access token (PAT) or SSH key instead of a password."
        if "repository not found" in lower or "could not find repository" in lower or "404" in msg:
            return "Repository not found. Check the URL and that you have access."
        if "connection refused" in lower or "could not resolve host" in lower or "failed to connect" in lower:
            return "Network error. Check your connection and try again."
        if "permission denied" in lower or "access denied" in lower or "denied" in lower:
            return "Access denied. Check credentials and repository permissions."
        if "already exists" in lower and "directory" in lower:
            return "Clone target directory already exists (a previous clone may have failed). Try again or use a different repo."
        return msg

    async def _check_git_available(self) -> tuple[bool, str]:
        """Return (True, '') if git is in PATH and works; else (False, error_message)."""
        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
        except FileNotFoundError:
            return (
                False,
                "Git is not installed or not in PATH. Install Git and ensure it is available where the backend runs (e.g. restart the backend from a shell where 'git --version' works).",
            )
        except asyncio.TimeoutError:
            return (False, "Git did not respond in time. Check that Git is installed and in PATH.")
        except Exception as e:
            logger.warning("Git check failed: %s", e)
            return (
                False,
                "Git could not be run. Install Git and ensure it is in PATH where the backend runs.",
            )
        if process.returncode != 0:
            err = (stderr or stdout or b"").decode("utf-8", errors="replace").strip() or "Unknown error"
            return (False, f"Git is not available: {err}")
        return (True, "")

    async def _clone_repo(self, url: str, target_path: Path, branch: Optional[str] = None) -> None:
        """Clone a git repository with timeout.

        Args:
            url: Git repository URL
            target_path: Where to clone
            branch: Optional branch to checkout

        Raises:
            FileNotFoundError: If git executable is not found
            RuntimeError: If clone fails or times out
        """
        cmd = ["git", "clone", "--depth", "1"]

        if branch:
            cmd.extend(["--branch", branch])

        cmd.extend([url, str(target_path)])

        logger.info(f"Cloning repository: {url}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise

        try:
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=CLONE_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                process.kill()
                if target_path.exists():
                    try:
                        shutil.rmtree(target_path)
                    except Exception as e:
                        logger.warning(f"Cleanup after timeout failed: {e}")
                raise RuntimeError(f"Clone timed out after {CLONE_TIMEOUT_SECONDS} seconds")

            if process.returncode != 0:
                err_bytes = stderr or stdout or b""
                try:
                    error_raw = err_bytes.decode("utf-8", errors="replace")
                except Exception:
                    error_raw = str(err_bytes)[:300]
                if target_path.exists():
                    try:
                        shutil.rmtree(target_path)
                    except Exception as e:
                        logger.warning(f"Cleanup after clone failure failed: {e}")
                normalized = self._normalize_clone_error(error_raw)
                raise RuntimeError(normalized)

            logger.info(f"Successfully cloned to {target_path}")

        except FileNotFoundError:
            raise

    def get_repo_path(self, repo_id: str) -> Optional[Path]:
        """Get the filesystem path for a connected repository.

        Args:
            repo_id: The connection ID

        Returns:
            Path to the repository, or None if not found
        """
        connection = self._connections.get(repo_id)
        if connection:
            path = Path(connection.path)
            if path.exists():
                return path
        return None

    def disconnect(self, repo_id: str) -> bool:
        """Disconnect and optionally cleanup a repository.

        For cloned repos: removes the cloned directory
        For local repos: just removes the connection

        Args:
            repo_id: The connection ID

        Returns:
            True if disconnected, False if not found
        """
        connection = self._connections.get(repo_id)
        if not connection:
            return False

        # Cleanup cloned repos
        if not connection.is_local:
            path = Path(connection.path)
            if path.exists():
                try:
                    shutil.rmtree(path)
                    logger.info(f"Removed cloned repository at {path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup clone at {path}: {e}")

        del self._connections[repo_id]
        logger.info(f"Disconnected repository: {connection.name} (id={repo_id})")

        return True

    def list_connections(self) -> list[RepoConnection]:
        """List all active repository connections.

        Returns:
            List of RepoConnection objects
        """
        # Validate connections still exist
        valid_connections = []
        for conn in self._connections.values():
            if Path(conn.path).exists():
                valid_connections.append(conn)
            else:
                # Auto-cleanup stale connections
                logger.warning(f"Cleaning up stale connection: {conn.id}")
                del self._connections[conn.id]

        return valid_connections

    def get_connection(self, repo_id: str) -> Optional[RepoConnection]:
        """Get a specific connection by ID.

        Args:
            repo_id: The connection ID

        Returns:
            RepoConnection if found and valid, None otherwise
        """
        connection = self._connections.get(repo_id)
        if connection and Path(connection.path).exists():
            return connection
        return None


# Global singleton instance
_repo_manager: Optional[RepoManager] = None


def get_repo_manager() -> RepoManager:
    """Get the global RepoManager instance."""
    global _repo_manager
    if _repo_manager is None:
        _repo_manager = RepoManager()
    return _repo_manager
