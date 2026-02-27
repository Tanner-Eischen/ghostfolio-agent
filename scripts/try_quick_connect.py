"""Try quick-connect to Tanner-Eischen/Ghostfolio; if Git not in PATH, prepend and retry."""
import asyncio
import os
import sys
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Git search paths (mirror manager logic)
GIT_SEARCH_PATHS = [
    Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Git" / "cmd" / "git.exe",
    Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Git" / "bin" / "git.exe",
    Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "Git" / "cmd" / "git.exe",
    Path("/usr/bin/git"),
    Path("/usr/local/bin/git"),
]


def prepend_git_to_path() -> bool:
    """Prepend Git directory to PATH if found in common locations. Returns True if PATH was updated."""
    import shutil
    if shutil.which("git"):
        return False  # already in PATH
    for p in GIT_SEARCH_PATHS:
        if p.exists():
            git_dir = str(p.parent)
            path_sep = ";" if os.name == "nt" else ":"
            current = os.environ.get("PATH", "")
            if git_dir not in current.split(path_sep):
                os.environ["PATH"] = git_dir + path_sep + current
                print(f"Prepend Git to PATH: {git_dir}", file=sys.stderr)
                return True
    return False


async def try_connect():
    from src.repo.manager import (
        get_repo_manager,
        RepoConnectionRequest,
        _GIT_EXE,
    )

    request = RepoConnectionRequest(
        source="https://github.com/Tanner-Eischen/Ghostfolio",
        name="Ghostfolio (Tanner)",
    )
    manager = get_repo_manager()

    out = await manager.connect(request)
    if out.success:
        print("OK", out.connection.name, out.connection.id)
        return True

    # If failure suggests Git not found, prepend Git to PATH and retry once
    err = (out.error or "").lower()
    if "git" in err and ("not installed" in err or "not in path" in err or "not found" in err):
        if prepend_git_to_path():
            # Force manager to re-resolve git executable
            import src.repo.manager as mod
            mod._GIT_EXE = None
            out2 = await manager.connect(request)
            if out2.success:
                print("OK (after adding Git to PATH)", out2.connection.name, out2.connection.id)
                return True
            print("FAIL (retry):", out2.error, file=sys.stderr)
        else:
            print("Git not found in common locations; cannot add to PATH.", file=sys.stderr)
    else:
        print("FAIL:", out.error, file=sys.stderr)
    return False


def main():
    ok = asyncio.run(try_connect())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
