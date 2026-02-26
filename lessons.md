# Lessons Learned

## 2026-02-26: Dashboard Repo Docking Workbench - Target Repository Connection

**Summary**
- Created RepoManager class for git cloning and local path validation
- Added 5 new API endpoints for repo connection lifecycle
- Parameterized analysis functions to work with any target repository
- Added RepoConnector component for frontend repo input

**Why**
- Dashboard was analyzing ghostfolio-agent's own `./src/` instead of user-provided target repos
- Users need to point the dashboard at any open source repo to analyze it
- Goal is to identify integration points where an agent could hook in

**What worked / what didn't**
- **Worked**: Using `asyncio.create_subprocess_exec` with timeout for git clone
- **Worked**: Path validation with blocked protocols and traversal detection
- **Worked**: Parameterizing analysis functions to accept `target_path: Path | None`
- **Worked**: Auto-detecting package name from target directory structure
- **Didn't**: Initial grid layout change broke div nesting - had to add extra closing tag

**Assumptions**
- Cloned repos go to `data/repos/{uuid}/` with 60-second clone timeout
- Local paths are validated but not copied (just registered)
- Analysis works for Python repos only (FastAPI, Flask route detection)
- Connection state is in-memory (lost on restart for MVP)

**Edge cases**
- Blocked `file://` protocol and embedded credentials in URLs
- Path traversal protection against `../` patterns
- Sensitive system directories blocked (`/etc`, `/root`, `C:\Windows`, etc.)
- Missing pyproject.toml falls back to git tags or default version

**Verification**
- `python -c "from src.repo.manager import RepoManager; print('OK')"` → OK
- `python -c "from src.api.routes import app; print('OK')"` → OK
- `cd frontend && npm run build` → builds successfully
- All 6 tasks completed in task list

**Follow-ups**
- [Optional] Add integration points detection endpoint (`GET /repo/{repo_id}/integration-points`)
- [Optional] Persist connections to file/database for restart survival
- [Optional] Add SSH URL support with key-based authentication
- [Required] Manual test with real git URL (e.g., `https://github.com/tiangolo/fastapi`)

---

## 2026-02-26: Dashboard Real Data Implementation - Replaced Hardcoded Values with AST Analysis

**Summary**
- Replaced hardcoded `/repo` endpoint values with real computed data
- Implemented AST-based Python import analysis for dependency graph
- Added helper functions: `_analyze_python_imports`, `_count_fastapi_endpoints`, `_count_tool_hooks`, `_detect_modules`, `_get_version`

**Why**
- Dashboard backend was returning fake data: version="v2.4.0", endpoints=24, services=8, tool_hooks=5
- Dependency graph showed static nodes/edges that didn't reflect actual code
- Users need to see real codebase metrics for trust and usefulness

**What worked / what didn't**
- **Worked**: `ast.parse()` for extracting `src.*` imports - simple and reliable
- **Worked**: `app.routes` iteration for counting FastAPI endpoints
- **Worked**: `pathlib.Path.rglob('*.py')` for recursive file discovery
- **Worked**: `get_tool_count()` from existing tools registry
- **Didn't**: Had to handle edge cases like `__pycache__` directories and files with syntax errors

**Assumptions**
- Module detection looks for directories in `src/` (not `__init__.py` presence)
- Version extraction checks pyproject.toml first, falls back to `git describe`
- Import analysis only tracks `src.*` imports (not external dependencies)
- Dependency edges are unidirectional based on who imports whom

**Edge cases**
- Files with syntax errors are silently skipped in import analysis
- `__pycache__` directories are excluded from module detection
- Git subprocess calls have 5-second timeout to prevent hanging
- Missing pyproject.toml falls back to git tags or default "v0.1.0"

**Verification**
- `python -c "from src.api.routes import _count_fastapi_endpoints; print(_count_fastapi_endpoints())"` → 30
- `python -c "from src.api.routes import _detect_modules; print(_detect_modules())"` → ['agent', 'api', 'tools', 'utils', 'verification']
- API `/repo` endpoint returns: endpoints=30, services=5, tool_hooks=3 (all real values)
- API `/repo/dependencies` returns: 7 nodes, 12 edges based on actual imports

**Follow-ups**
- [Optional] Add external dependency tracking (PyPI packages)
- [Optional] Cache dependency analysis results for performance
- [Optional] Add file-level granularity to dependency graph

---

## 2026-02-26: Backend Real Implementation - Wiring Mock Endpoints to Real Services

**Summary**
- Connected 7 mock/stub API endpoints to actual backend services
- Created 4 new utility modules: config_store, langsmith_client, usage_tracker, registry
- Created evals/runner_api.py for API-friendly eval access
- All 5 phases completed: Verification Config, LangSmith Traces, Evals Framework, Usage Tracking, Tool Registry

**Why**
- React UI was built with mock endpoints returning hardcoded data
- Real implementations existed but weren't connected to the API
- Need actual observability, evaluation, and cost tracking for production

**What worked / what didn't**
- **Worked**: Using LangSmith SDK Client for trace retrieval - `client.list_runs()` and `client.read_run()`
- **Worked**: JSON file-based config storage is simple and adequate for single-instance deployment
- **Worked**: Token usage extraction from LangChain AIMessage `response_metadata.token_usage`
- **Worked**: Reusing existing eval runner with thin API wrapper in evals/runner_api.py
- **Didn't**: LangSmith SDK child run query syntax is different from expected - used query string filter instead

**Assumptions**
- Config storage uses JSON files in `data/` directory (acceptable for MVP, not distributed)
- Token tracking relies on LangChain providing usage metadata (may not work with all models)
- Tool registry is static (tools discovered at startup from ALL_TOOLS list)
- Cost projections use historical averages if available, otherwise gpt-4o-mini estimates

**Edge cases**
- LangSmith `list_runs()` returns a generator, must convert to list
- AIMessage `response_metadata` structure varies by provider
- Config store handles missing files by creating with defaults
- Usage tracker gracefully handles unknown models (defaults to gpt-4o-mini pricing)

**Verification**
- `python -c "from src.api.routes import app"` - routes module loads
- `python -c "from src.utils.config_store import ..."` - all modules load
- `python -c "from src.tools.registry import list_tools; print(len(list_tools()))"` - returns 3
- `python -c "from evals.runner_api import list_eval_cases; print(len(list_eval_cases()))"` - returns 10

**Follow-ups**
- [Optional] Add Redis backing for config store for multi-instance deployments
- [Optional] Add background eval running with WebSocket status updates
- [Optional] Add more detailed token tracking per tool call
- [Required] Test end-to-end with real LangSmith API credentials

---

## 2026-02-26: 7-Screen UI Migration from Streamlit to React

**Summary**
- Migrated from Streamlit frontend to a 7-screen React SPA with Vite + TailwindCSS
- Created shared navigation shell (Layout, Navigation, Sidebar, AlertBar components)
- Added 11 new backend API endpoints for all 7 pages
- Frontend builds successfully with TypeScript and Tailwind CSS v4

**Why**
- Original Streamlit app was a single-page prototype
- Need a production-ready UI with proper routing and state management
- Stitch templates provided design direction for 7 distinct pages

**What worked / what didn't**
- **Worked**: Vite + React + TypeScript setup was straightforward
- **Worked**: Extracting components from Stitch HTML templates directly into React
- **Worked**: Tailwind CSS v4 with `@tailwindcss/postcss` plugin
- **Didn't**: Initial attempt to use `npx tailwindcss init` failed - had to create config manually
- **Didn't**: TypeScript `verbatimModuleSyntax` required `type` imports for type-only imports

**Assumptions**
- Backend endpoints return mock data for now (traces, evals, finances)
- In-memory storage for strategy and verification config (will need persistence)
- LangSmith integration for traces can be added later via API client

**Edge cases**
- TypeScript requires `type` keyword for type-only imports when `verbatimModuleSyntax` is enabled
- Tailwind CSS v4 requires `@tailwindcss/postcss` package (not `tailwindcss` directly)
- React `unknown` types from `Object.entries` need explicit casting with `String()`

**Verification**
- `cd frontend && npm run build` - builds successfully
- `pytest tests/` - 435 tests collected, most pass (some pre-existing failures unrelated to this change)

**Follow-ups**
- [Optional] Add real LangSmith API integration for traces
- [Optional] Persist strategy/verification config to file or database
- [Optional] Add authentication/authorization to new endpoints
- [Required] Deploy frontend build to production (update Railway config)

---

# Template for Future Entries

```md
## YYYY-MM-DD: <short title>

**Summary**
-

**Why**
-

**What worked / what didn't**
-

**Assumptions**
-

**Edge cases**
-

**Verification**
-

**Follow-ups**
-
```
