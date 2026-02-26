---
name: Page 5 Observability
overview: "Implement Page 5 (Observability / Traces): add trace list and trace detail endpoints (LangSmith API or own DB), wire the Stitch Observability UI (trace list, detail view, search). Assumes Page 1–4 and shared Integrator shell are in place."
todos: []
---

# Page 5: Observability (Agent Traces)

## Scope and context

- **Focus**: View and inspect agent runs (traces) — list recent traces, open trace detail (steps, tool calls, tokens, errors). Universal observability; domain shows up in trace content.
- **Existing**: LangSmith tracing is enabled ([src/utils/config.py](src/utils/config.py), [src/agent/](src/agent/)). Stitch HTML at [stitch-downloads/3023668461815052031/eacf252cf36f4314a46c709a638cfd00-Agent-Trace-Observability-Deep-Dive.html](stitch-downloads/3023668461815052031/eacf252cf36f4314a46c709a638cfd00-Agent-Trace-Observability-Deep-Dive.html) (Agent Trace Observability).
- **Goal**: Add **GET /traces** (list, with optional filters) and **GET /traces/{trace_id}** (detail). Wire Stitch Observability UI; data can come from LangSmith API or a local/cached store.

---

## 1. Backend: Trace endpoints

- **GET /traces**: Query params e.g. `limit`, `status` (success/failure), `agent` (optional). Returns list of trace summaries: `trace_id`, `name` or `run_type`, `status`, `duration_ms`, `token_count`, `timestamp`.
- **GET /traces/{trace_id}**: Returns full trace detail: steps, tool calls, inputs/outputs, token usage, error if any. Structure matches what UI needs (nested steps, tool_calls array).
- **Data source**: (1) **LangSmith API**: call LangSmith REST API with LANGCHAIN_API_KEY to list runs and get run by ID. (2) **Local/cache**: persist runs in DB or file if not using LangSmith. Prefer LangSmith for MVP if key is configured.
- **Tests**: Test GET /traces returns list shape; GET /traces/{id} returns detail shape (mock or skip if LangSmith required).

---

## 2. Frontend: Observability screen

- **Stitch reference**: [eacf252cf36f4314a46c709a638cfd00-Agent-Trace-Observability-Deep-Dive.html](stitch-downloads/3023668461815052031/eacf252cf36f4314a46c709a638cfd00-Agent-Trace-Observability-Deep-Dive.html) — Recent Traces sidebar, trace detail (steps, tool calls, tokens), search by trace ID.
- **Wire**: On load, GET /traces and render list; on trace click, GET /traces/{id} and render detail. Search box filters list or fetches by ID.
- **Navigation**: Observability is Page 5 in shared Integrator nav.

---

## 3. Data flow

- Page load → GET /traces → render trace list.
- User selects trace → GET /traces/{trace_id} → render detail (steps, tools, tokens).
- Search → filter list or GET /traces?trace_id=... if supported.

---

## 4. Files to touch

| Area | File | Change |
|------|------|--------|
| Backend | [src/api/routes.py](src/api/routes.py) | Add GET /traces, GET /traces/{trace_id}. Optional: [src/utils/langsmith_client.py](src/utils/langsmith_client.py) or similar to call LangSmith API. |
| Config | [src/utils/config.py](src/utils/config.py) | LangSmith base URL / project already present; ensure workspace or project filter if needed. |
| Tests | [tests/test_api/test_routes.py](tests/test_api/test_routes.py) | Test /traces list and /traces/{id} structure (mock LangSmith if needed). |
| Frontend | `frontend/` (Observability page) | Add Observability HTML from Stitch; JS to fetch /traces and /traces/{id}; wire list and detail. |

---

## 5. Out of scope

- Writing traces from backend (agent already sends to LangSmith).
- Real-time tailing (polling or WebSocket later).
- Other pages.

---

## 6. Implementation order

1. Backend: Add LangSmith client or adapter; GET /traces and GET /traces/{trace_id}.
2. Tests: Add route tests (mock LangSmith responses if needed).
3. Frontend: Add Observability page from Stitch; wire trace list and detail to endpoints.
