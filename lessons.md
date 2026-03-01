# Lessons Learned

---

## Quick Reference: Patterns to Avoid

1. **Mock data as fallback** - Hides problems. Use real data or proper empty states.
2. **FastAPI route ordering** - Parameterized routes (`/repo/{id}`) shadow static routes (`/repo/dependencies`). Define static routes FIRST.
3. **useEffect without cleanup** - Causes memory leaks and setState on unmounted components. Always use `mountedRef` pattern.
4. **Race conditions from rapid requests** - Use abort refs to track latest request ID and ignore stale responses.
5. **parseInt without validation** - Produces NaN breaking calculations. Always validate: `const val = parseInt(x) || default`.
6. **No-op string operations** - `replace("-", "-")` does nothing. Verify regex/replace logic.
7. **Stale closure in React setState** - Use functional updates: `setState(prev => ...)` not `setState(value)`.
8. **HTTP 200 with error body** - Use proper HTTP status codes (400, 500) with `HTTPException`.
9. **Overly broad security blocks** - `C:\Users` blocking prevented legitimate local repo connections.
10. **Missing null guards** - `Object.keys(toolCall.args)` crashes when args is null/undefined.
11. **Type-only imports without `type`** - TypeScript `verbatimModuleSyntax` requires `import type { X }`.
12. **Extracting from wrong location** - Backend tool_calls was empty because extraction looked at wrong field.
13. **ReactFlow without provider** - `useReactFlow()` hook crashes without `ReactFlowProvider` wrapper.
14. **Polling without cleanup** - `setInterval` in useEffect must be cleared on unmount.

---

## Quick Reference: Proven Solutions

**React/TypeScript:**
- `mountedRef` pattern: `const mounted = useRef(true); useEffect(() => { return () => { mounted.current = false; }; }, []);`
- AbortController for cancellation: `const abortRef = useRef(0); const requestId = ++abortRef.current; if (requestId !== abortRef.current) return;`
- `useMemo` for filtered lists, `useCallback` for handlers - prevents unnecessary recalculations
- `crypto.randomUUID()` for secure session IDs
- Debounced scroll (100ms) prevents UI lag during rapid updates
- Toast notifications for all async operations (success/error feedback)

**Backend (FastAPI/Python):**
- `_normalize_error()` pattern maps stderr/exceptions to user-friendly messages
- AST parsing for import/route detection: `ast.parse()` + `ast.Import` / `ast.ImportFrom`
- `pathlib.Path.rglob('*.py')` for recursive file discovery
- `asyncio.create_subprocess_exec` with 60s timeout for git operations
- JSON file config storage (`data/*.json`) for single-instance MVP deployments
- Session TTL tracking with cleanup on each request prevents memory leaks

**LangChain/LangSmith:**
- `get_current_run_tree()` from `langsmith.run_helpers` for run_id inside `@traceable` methods
- Token usage from `AIMessage.response_metadata.token_usage`
- Child run query: `client.list_runs(filter=f"eq(parent_run_id, '{run_id}')")`
- `@tool` decorator for LangChain tools with `args_schema` for structured params

**Architecture:**
- Reuse existing patterns for consistency (e.g., GeneratedToolStore follows FeedbackStore pattern)
- Dynamic imports via `importlib.util.spec_from_file_location` for runtime-loaded modules
- ReactFlow + dagre for auto-layout dependency graphs
- Static route definitions before parameterized in FastAPI

---

## 2026-03-01: Chat behavior – conversational style and tool use

**Summary**
- Updated `SYSTEM_PROMPT` in `src/agent/prompts.py` so the agent responds in a natural, conversational (LLM chat-style) way and is explicitly instructed to call tools when the user asks about portfolio, market data, or trends.
- Clarified when to use tools (portfolio value/holdings/risk/diversification → `portfolio_analysis`/`risk_assessment`; price or history for a symbol → `market_data_lookup`/`price_history`; trending crypto → `trending_crypto`) and when to answer from knowledge only (general questions, setup, greetings).
- Aligned `TOOL_SELECTION_PROMPT` with the same triggers.

**Why**
- Agent should feel like a normal chat API (conversational replies) and must use tools for market/portfolio/trends instead of answering from memory.

**Assumptions**
- Tool-calling is entirely LLM-driven; prompt changes are the main lever. No `tool_choice` or middleware used.

**Verification**
- Lint on `src/agent/prompts.py` clean; existing tests that assert `TOOL_SELECTION_PROMPT` contains `portfolio_analysis`/`risk_assessment` still pass.

**Follow-ups**
- Optional: add evals or manual checks that portfolio/market/trend queries result in tool_calls and conversational final reply.

---

## 2026-03-01: API key loading – .env path and pydantic compatibility

**Summary**
- **Root cause 1 (CWD):** `env_file=".env"` in pydantic_settings is resolved relative to the process **current working directory**. If the server or script is started from `frontend/`, another repo, or an IDE with a different cwd, `.env` was never found and `OPENAI_API_KEY` stayed empty.
- **Fix 1:** In `src/utils/config.py`, `.env` is now resolved to an **absolute path** from the config file location: `Path(__file__).resolve().parent.parent.parent / ".env"` (project root = directory containing `src/`). Settings load the same regardless of cwd.
- **Root cause 2 (import error):** `pydantic_settings` 2.13 imports `Secret` from `pydantic`. That type exists only in **pydantic >= 2.7** (and was stabilized later). With pydantic 2.6.4 (e.g. in user site-packages), `ImportError: cannot import name 'Secret'` breaks the whole config module, so the app never loads the key.
- **Fix 2:** `requirements.txt` now pins `pydantic>=2.10.0` so a clean install matches pydantic-settings. If the environment already has an older pydantic, upgrade with `pip install "pydantic>=2.10.0"` (may require closing other Python processes or using a venv).
- **Fallback:** A `model_validator(mode="before")` in Settings reads `.env` manually via `_read_env_key("OPENAI_API_KEY")` when the key is still empty after pydantic’s load (e.g. path quirks or older pydantic), so the key can still be injected without adding python-dotenv.
- **Check script:** `scripts/check_openai_key.py` verifies key presence in `.env` using the same project-root path; it also tries `get_settings()` and reports if config failed to load the key (e.g. due to pydantic version).

**Why**
- Users saw “API key isn’t configured” even with `OPENAI_API_KEY` set in `.env` when running from a different cwd or with an incompatible pydantic install.

**Assumptions**
- Project layout is `project_root/src/utils/config.py` and `.env` at project root. No extra dependency for the fallback (we parse `.env` ourselves).

**Edge cases**
- If upgrading pydantic fails (permission or conflicting deps), use a dedicated venv with `pip install -r requirements.txt` so pydantic and pydantic-settings versions match.

**Verification**
- Lint on `config.py` clean. Run `python scripts/check_openai_key.py` from project root and from `frontend/` with `PYTHONPATH` set to project root: key should be reported as loaded when pydantic is compatible.

**Follow-ups**
- Optional: add a health-check or startup log that confirms `openai_api_key` is non-empty so misconfiguration is visible in logs.

---

## 2026-02-28: Session persistence for chat history

**Summary**
- Added `src/utils/session_store.py`: `SessionStore` persists sessions under `data/sessions/` (index.json + one JSON file per session, keyed by hash of session_id). Uses LangChain `messages_to_dict` / `messages_from_dict` for message serialization.
- Agent uses `SessionStore` in `core.py`: loads session from store when not in memory (`_ensure_session_loaded`), saves after each turn (`save_history`), `list_sessions` and `clear_conversation` delegate to store; added `get_session_history(session_id)` for API (loads from store then returns messages).
- GET `/sessions/:id` now uses `agent.get_session_history()` and filters to HumanMessage/AIMessage only for display.

**Why**
- Chat history should survive server restarts.

**Assumptions**
- Single process; `data/` already in .gitignore so session files are not committed.

**Verification**
- Manual test: save/load/list/delete in SessionStore; lints clean.

**Follow-ups**
- Optional: TTL cleanup of old session files; optional backup/export.

---

## 2026-02-28: Chat history / past conversations

**Summary**
- Backend: `GET /sessions` returns list of sessions (session_id, message_count, last_accessed) from agent’s `list_sessions()`; response models `SessionSummary`, `SessionsListResponse`.
- Frontend: `sessionsApi.list()` in client; AgentWorkspace has “History” button in the slim bar that opens a drawer with “New chat” and a list of past sessions; selecting a session loads it via `GET /sessions/:id` and sets sessionId + messages so the user can view/continue that thread.

**Why**
- Users need a way to access and resume past conversations.

**What worked / what didn’t**
- Reusing existing `GET /sessions/{session_id}` for loading one session; adding a dedicated list endpoint kept list vs get semantics clear.

**Assumptions**
- History is in-memory only (agent’s `_conversation_history`); no persistence across server restarts.

**Edge cases**
- Empty list shows “No past conversations”; loading a session on error shows toast and leaves drawer open.

**Verification**
- Lint clean on routes.py, client.ts, AgentWorkspace.tsx.

**Follow-ups**
- Optional: persist sessions to disk/DB for durability.

---

## 2026-02-28: README and docs reframed for service model

**Summary**
- README now addresses two audiences: end users (only need Ghostfolio access key) and service providers (run the stack, set env vars, use Observability & Cost page).
- Added "For people using the service" and "Using the hosted app"; reframed Quick Start as "For service providers / self-hosting"; Configuration and AI Cost Analysis explicitly for providers; Deployment note that end users only need Ghostfolio key.
- .env.example: top comment for service providers; section headers (Required, Optional/Observability, Ghostfolio default connection).
- docs/COST_ANALYSIS.md: purpose/audience line for service providers; frontend/README: one-line pointer to root README.

**Why**
- Product is offered as a hosted service; provider fronts compute and uses cost page for projections; end users should not see install/API-key instructions.

**Verification**
- Read-through of README, .env.example, docs/COST_ANALYSIS.md, frontend/README.md.

---

## 2026-02-28: requirements.txt Audit (Trim Unused Deps)

**Summary**
- Removed 4 packages that are not imported or used: `langchain-anthropic`, `anthropic`, `tenacity`, `python-dotenv`.
- Kept all packages that are directly used in `src/` and `evals/`.

**Why**
- Smaller install surface, faster venv/CI; fewer version conflicts (e.g. pydantic/core).

**What worked / what didn’t**
- **Checked**: Agent uses `ChatOpenAI` only (`src/agent/core.py`); `anthropic_api_key` exists in config for future use but no Anthropic imports.
- **Checked**: Retry logic is custom in `ghostfolio.py` / `coingecko.py`; no `tenacity` import.
- **Checked**: Config uses `pydantic_settings` with `env_file=".env"`; pydantic-settings loads `.env` itself, no `load_dotenv()` in code.

**Assumptions**
- If Anthropic is added later, add back `langchain-anthropic` and `anthropic`.
- `openai` kept as explicit dependency (also pulled by `langchain-openai`) for clarity/pinning.

**Verification**
- `pip install -r requirements.txt` in a clean venv; `python -c "from src.api.routes import app"` succeeds.

**Follow-ups**
- Optional: add `requirements-optional.txt` with `langchain-anthropic`, `anthropic`, `python-dotenv` for future use.

---

## 2026-02-28: Agent Tool Call Performance Improvements

**Summary**
- Parallelized verification pipeline: market data freshness, fact checks, and citation verification now run via `asyncio.gather()` instead of sequentially.
- Parallelized fact-check claims: up to 5 `verify_claim()` calls in `_run_fact_checks` run in parallel with `asyncio.gather()`.
- Added httpx connection limits and timeouts for Ghostfolio, Yahoo Finance, and CoinGecko clients: `Timeout(30/10/15s, connect=10/5/5s)`, `Limits(max_keepalive_connections=6–8, max_connections=12–16, keepalive_expiry=20–30s)` to reuse connections and fail fast on connect.

**Why**
- Single-tool latency was ~5.1s (G4 target &lt;5s); verification and I/O were sequential. Reducing verification wall time and improving connection reuse should lower end-to-end latency for agent tool calls.

**What worked / what didn't**
- **Worked**: All 35 verification pipeline tests pass. No API contract changes; parallelization is internal to the pipeline.
- **Worked**: Explicit `httpx.Timeout` and `httpx.Limits` are valid for `AsyncClient`; connect timeout shortens time to first failure on slow networks.

**Assumptions**
- Verification steps (market freshness, fact checks, citations) are independent given `response` and `tool_outputs`; confidence scoring correctly uses the gathered results.
- Keepalive limits are sized for single-agent usage (not hundreds of concurrent connections).

**Edge cases**
- When `tool_outputs` is empty, `_market_freshness` and `_citations` return `([], [])` and `None`; no extra work.
- Empty `sentences` in `_run_fact_checks`: `asyncio.gather()` with no tasks returns `[]`; we use `if tasks:` before gathering.

**Verification**
- `pytest tests/test_verification/test_pipeline.py -v` — 35 passed.

**Follow-ups**
- Optional: run evals and compare `average_response_time_ms` before/after to quantify improvement.
- Optional: add a small TTL cache for repeated identical tool inputs (e.g. same portfolio query within 60s) if further latency reduction is needed.

---

## 2026-02-28: Load All Tools, Evals, Performance (G4 Week 2 Plan)

**Summary**
- Loaded all 5 domain tools: added `transaction_categorize` and `compliance_check` to `CORE_TOOLS` in `src/tools/__init__.py`.
- Added 6 eval cases to `mvp_evals.json`: 3 edge (MVP-070–072), 3 multi-step (MVP-073–075); edge_case and multi_step now ≥10 each.
- Eval report: added `avg_response_time_ms_single_tool`, `avg_response_time_ms_multi_step`, `tool_success_count`, `tool_total_count`, `tool_success_rate`; printed and saved in JSON.
- New check types: `response_time_ms` (max ms), `confidence_min` (min confidence) in `run_evals.py` and validation.
- GET `/metrics`: chat request count and latency p50/p95/avg from last 100 requests (in-memory, reset on restart).

**Why**
- G4 Week 2 AgentForge requires minimum 5 tools, 10+ edge and 10+ multi-step cases, and performance visibility (latency, tool success).
- No separate “tool creation” skill for Python tools; write-skills is for SKILL.md definitions. The two tools already existed; only wiring was needed.

**What worked / what didn't**
- **Worked**: Adding the two tools to `CORE_TOOLS` and `__all__`; all 75 evals passed (100%), including new multi-step cases using compliance_check and transaction_categorize.
- **Worked**: Classifying single-tool vs multi-step by `len(eval_case.expected_tool_calls)`; tool success = no errors and `len(tool_outputs) >= len(tool_calls)` per result.
- **Worked**: In-memory deque(maxlen=100) for latency samples and simple counter; GET /metrics returns p50/p95/avg without external infra.

**Assumptions**
- Metrics are process-local; multi-worker deployments would need a shared store for aggregate metrics.
- Eval tool success counts “all tools had outputs” per case; does not distinguish partial tool failure within a case.

**Edge cases**
- No samples yet: `/metrics` returns null for latency fields.
- PowerShell: use `;` not `&&` for chained commands.

**Verification**
- `python evals/run_evals.py --category mvp --validate` (75 cases valid).
- `python evals/run_evals.py --category mvp --save`: 75/75 passed, edge_case 11, multi_step 11, tool success 100%.
- GET /metrics returns chat_request_count and latency_* when requests have been made.

**Follow-ups**
- Optional: Add one or two eval criteria with `response_time_ms` (e.g. 15000) or `confidence_min` (e.g. 50) for SLO regression.

---

## 2026-02-28: Add '+' Button to Register Generated Tools

**Summary**
- Preserved 3 Ghostfolio core tools: `portfolio_analysis`, `market_data_lookup`, `risk_assessment`
- Created `src/tools/generated_store.py` - Thread-safe persistence layer for storing generated tools in `data/generated_tools/` directory
- Created `src/tools/code_validator.py` - Safety validation for generated code (AST parsing, @tool decorator check, forbidden import blocking)
- Modified `src/tools/registry.py` - Added `register_generated_tool()`, `get_all_tools()` returning CORE_TOOLS + generated tools
- Modified `src/tools/__init__.py` - Added dynamic loading via `get_all_tools()` while keeping `CORE_TOOLS` as the base
- Modified `src/agent/core.py` - Added `reload_tools()` method and `reload_agent_tools()` function to refresh agent tool set
- Modified `src/api/routes.py` - Added `POST /tools/register` endpoint that validates, persists, loads, and reloads agent
- Modified `frontend/src/api/client.ts` - Added `ToolRegistrationRequest`, `ToolRegistrationResponse` types and `toolsApi.register()` method
- Modified `frontend/src/pages/AgentChat.tsx` - Added green "Register Tool" button with '+' icon in generated tool modal

**Why**
- Generated tool suggestions were dead-end - they produced code strings but never registered them with the agent
- Users could see generated code but couldn't actually use it in the agent
- Need a way to persist dynamically generated tools across server restarts
- Keep Ghostfolio-specific tools as the base, allow repo-specific tools as extensions

**What worked / what didn't**
- **Worked**: Following the FeedbackStore pattern for the GeneratedToolStore made implementation consistent
- **Worked**: Using AST validation to catch syntax errors before persisting
- **Worked**: Clearing the tool cache on registration to force reload
- **Worked**: Using dynamic import via `importlib.util` to load generated tools at runtime

**Assumptions**
- Generated tools use the LangChain `@tool` decorator
- Tools are stored in `data/generated_tools/` directory with registry.json for metadata
- Tool names are sanitized to valid Python identifiers

**Edge cases**
- Duplicate tool names: Rejected with error
- Invalid syntax: Validate before save, reject with details
- Dangerous imports: Block `os`, `subprocess`, `sys`, `socket`, etc.
- Server restart: Load all tools from disk on startup
- Tool crashes: Catch exception, don't crash agent

**Verification**
- `python -c "from src.tools.generated_store import get_generated_tool_store"` - OK
- `python -c "from src.tools.registry import register_generated_tool, get_all_tools"` - OK
- `python -c "from src.agent.core import reload_agent_tools"` - OK
- Core tools verified: `['portfolio_analysis', 'market_data_lookup', 'risk_assessment']`
- API routes `/tools/register` and `/tools/generated/{tool_name}` registered
- Frontend Vite dev server started successfully (no TypeScript errors)

**Follow-ups**
- Optional: Add unit tests for generated tool registration flow
- Optional: Add UI to manage/delete generated tools from the Tools tab

---

## 2026-02-28: Verification & Evaluations Page Deep Dive

**Summary**
- Added collapsible "How Verification Works" section documenting the 4-gate system (Syntactic, Temporal, Cross-Source, Economic Plausibility)
- Enhanced verification layer toggles with "If disabled" impact warnings explaining consequences
- Added check type legend explaining all eval check types (tool_called, field_present, verification_gate, etc.)
- Transformed eval results table into expandable cards showing criteria results with expected vs actual values
- Updated backend `format_results_for_api()` to return full eval data: input, response, tool_calls, tool_call_details, tool_outputs, confidence, criteria_results
- Added `EvalCriterionResult` and `ToolCallDetail` types to frontend API client

**Why**
- User wanted more transparency on the Verification & Evaluations page:
  1. Verification layers needed clear documentation of what each check does and what happens when disabled
  2. Eval results needed expandable sections showing expected vs actual tool calls/responses
- Previously, the page showed toggles with brief descriptions but lacked depth on verification gates
- Eval results showed pass/fail but hid detailed criteria results and actual data returned

**What worked / what didn't**
- **Worked**: Backend already saved rich data in JSON reports; only needed to expose it in the API response
- **Worked**: Creating reusable components (`EvalResultCard`, `CriterionResult`, `VerificationDocsSection`, `CheckTypeLegend`) kept the main component clean
- **Worked**: Using constant objects for gate descriptions and layer configs made data-driven rendering simple
- **Worked**: Color-coding criteria (emerald for pass, red for fail) makes results scannable

**Assumptions**
- Users want to see all criteria details, not just pass/fail summary
- Tool outputs can be displayed as JSON (may be large but scrollable)
- Verification gate documentation is valuable enough to take up vertical space

**Edge cases**
- Criteria with no results (pending tests) handled gracefully
- Empty tool_calls/tool_outputs arrays don't render sections
- Long values truncated with ellipsis and title tooltip for full content
- null/undefined expected/actual values display as "null"

**Verification**
- `cd frontend && npm run build` - builds successfully (6.87s)
- Backend changes are additive only - no breaking changes to existing API consumers

**Follow-ups**
- [Optional] Add JSON syntax highlighting for tool outputs
- [Optional] Add copy-to-clipboard for tool outputs
- [Optional] Filter results by pass/fail status
- [Optional] Export individual eval result as JSON

---

## 2026-02-27: UI/UX Fixes Across All Pages (Plan Implementation)

**Summary**
- Fixed ToolCallDropdown crash when `toolCall.args` is null/undefined (AgentChat).
- Made warning banner dismissible with X button and persisted dismissal in localStorage (AlertBar + Layout).
- Raised React Flow Controls z-index so zoom/fit buttons are clickable (DependencyGraph).
- Wired "View in LangSmith" button to open trace URL in new tab; base URL from env or default (ObservabilityCost).
- Added toast on New Chat and loading + toast on Generate buttons (AgentChat).
- Formatted category filter labels as Title Case (VerificationEvals).
- Removed link styling from entry points and removed duplicate warning banner (RepoAnalysis).
- Clarified tool checkboxes with helper text and tooltip (AgentChat Tools tab).

**Why**
- Browser-agent audits found sloppy UI, non-functional buttons, crashes, and unclear behavior; plan requested durable, simple fixes.

**What worked / what didn't**
- **Worked**: Null guard `toolCall.args && typeof toolCall.args === 'object'` before `Object.keys()`. Layout reads/writes `ghostfolio-agent-alert-dismissed` in localStorage; AlertBar receives `onDismiss`. Controls use `!z-50`. LangSmith URL `${LANGSMITH_BASE}/r/${traceId}` with optional `VITE_LANGSMITH_BASE_URL`. `generatingToolId` state for Generate buttons with spinner and toasts.

**Assumptions**
- LangSmith default base opens a valid project/runs page; user can set `VITE_LANGSMITH_BASE_URL` for custom project. Tool checkboxes remain for list visibility only; backend does not yet use selectedToolIds.

**Edge cases**
- localStorage may be unavailable (try/catch in Layout). Copy session ID already had showToast; New Chat and Generate now have feedback.

**Verification**
- ReadLints on all modified files: no errors.

**Follow-ups**
- [Optional] Backend to honor tool enable/disable from selectedToolIds. [Optional] React Flow edge handle IDs if "source handle id: null" console errors persist.

---

# Maintenance Instructions

When adding a new entry, follow this rotation:

1. **Add new entry at the top** (after the Quick Reference sections)
2. **Archive the oldest full entry** by extracting:
   - Mistakes → add to "Patterns to Avoid" (if not already covered)
   - Successes → add to "Proven Solutions" (if not already covered)
3. **Delete the archived full entry**
4. **Keep only 3 full entries** at any time

Example: If adding a 2026-03-01 entry when you have entries from 02-28, 02-28, and 02-27:
- Extract patterns from the 02-27 entry into Quick Reference
- Delete the full 02-27 entry
- Add the new 03-01 entry at top

This keeps the file lean while preserving institutional knowledge.

---

# Template for New Entries

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
