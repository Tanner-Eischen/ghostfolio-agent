---
name: Page 2 Strategy
overview: "Implement Page 2 (Strategy & Architecture) as an interactive, guided flow: use the repo connected in Page 1 and codebase analysis to recommend and guide architectural and model choices. Transparent recommendations; user can accept or override. Assumes Page 1 (Dashboard/Repo) and shared Integrator shell are in place."
todos: []
---

# Page 2: Strategy & Architecture (Guided, repo-aware)

## Scope and context

- **Focus**: **Interactive and engaging** — Page 2 guides the user through which architectural and model choices to make **based on the repo they just connected in Page 1** and the information gained there (codebase structure, dependency mapping, injection points, language/framework detected). Transparent: show why a framework or model is recommended; user can accept recommendations or change choices.
- **Existing**: FastAPI backend; Page 1 exposes `/repo` and (from code.html) codebase analysis. Stitch HTML at [5060997631a5485e9bd267bf6e4bb240-Agent-Strategy-Framework-Selection.html](stitch-downloads/3023668461815052031/5060997631a5485e9bd267bf6e4bb240-Agent-Strategy-Framework-Selection.html) (Agent Strategy & Architecture Hub).
- **Goal**: Backend exposes **repo-aware recommendations** (e.g. `GET /strategy/recommendations` or recommendations embedded in `GET /repo`/analysis). Strategy UI is a **guided flow**: show recommendations with short rationale (e.g. "Your repo uses Python + FastAPI; LangGraph fits well"), let user step through framework → model → pathways; persist with GET/POST **/strategy**. Save/Load Preset via **/presets** later.

---

## 1. Backend: Strategy config + repo-aware recommendations

- **GET /strategy**: Returns current config (framework, model, temperature, etc.).
- **POST /strategy**: Persists user’s choices (same shape).
- **Recommendations**: Either (a) **GET /strategy/recommendations** that takes repo context (or uses last analysis from Page 1) and returns e.g. `recommended_framework`, `recommended_model`, `rationale` (short text), or (b) **GET /repo** (or codebase-analysis endpoint) includes a `strategy_recommendations` block. Backend uses simple rules: e.g. Python + async → LangGraph; TypeScript/Nest → other; repo size/complexity → model tier. Transparent rationale for each suggestion.
- **Persistence**: In-memory or file for config; recommendations computed from repo/analysis data (no separate store).
- **Tests**: GET /strategy structure; POST updates; GET /strategy/recommendations returns structure when repo/analysis available.

---

## 2. Frontend: Guided Strategy screen

- **Stitch reference**: [5060997631a5485e9bd267bf6e4bb240-Agent-Strategy-Framework-Selection.html](stitch-downloads/3023668461815052031/5060997631a5485e9bd267bf6e4bb240-Agent-Strategy-Framework-Selection.html) — Framework Selection Matrix, model/config controls, Save Configuration, Load Preset.
- **Interactive flow**: On load, fetch repo/analysis context (from Page 1 or GET /repo) and GET /strategy/recommendations. Display **guided steps**: (1) Framework — show recommendation + rationale, user selects or keeps default; (2) Model — same; (3) Contribution pathways / options. Show why each recommendation fits the connected repo (transparent). Save → POST /strategy. Load Preset → /presets when available.
- **Navigation**: Strategy is Page 2 in shared Integrator nav; user arrives here after connecting repo on Page 1 so recommendations have context.

---

## 4. Files to touch

| Area | File | Change |
|------|------|--------|
| Backend | [src/api/routes.py](src/api/routes.py) | Add GET/POST /strategy; add GET /strategy/recommendations (or embed in /repo/analysis) using repo context. StrategyResponse/Request; recommendation rationale. |
| Tests | [tests/test_api/test_routes.py](tests/test_api/test_routes.py) | Test GET/POST /strategy; test recommendations shape. |
| Frontend | `frontend/` (Strategy page) | Guided flow: fetch repo context + recommendations; show steps with rationale; accept/override; POST /strategy. Save/Load Preset. |

---

## 5. Out of scope

- Full /presets CRUD (stub or later plan).
- Deep codebase analysis (Page 1 may expose minimal analysis; recommendations can use repo language/framework only for MVP).
- Other pages (Tool Library, Verification, etc.).

---

## 6. Implementation order

1. Backend: Add GET/POST /strategy; add GET /strategy/recommendations (or extend /repo/analysis) with repo-aware logic and rationale.
2. Tests: Add route tests for /strategy and recommendations.
3. Frontend: Add Strategy page as guided flow; fetch repo context + recommendations; show steps with transparent rationale; POST /strategy; Save/Load Preset placeholders.
