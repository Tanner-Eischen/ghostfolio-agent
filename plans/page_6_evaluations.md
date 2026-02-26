---
name: Page 6 Evaluations
overview: "Implement Page 6 (Evaluations): add eval run and results endpoints, wire the Stitch Systematic Evaluation Dashboard (run tests, pass rate, category breakdown, export). Replaces or complements previous Streamlit eval UI. Assumes Page 1–5 and shared Integrator shell are in place."
todos: []
---

# Page 6: Evaluations (Systematic Eval Framework)

## Scope and context

- **Focus**: Run and view systematic eval results — pass rate, hallucination rate, latency KPIs, per-case and per-category results. Universal eval framework; finance-specific cases live in [evals/](evals/).
- **Existing**: [evals/run_evals.py](evals/run_evals.py) runs MVP evals and can save report JSON. Stitch HTML at [stitch-downloads/3023668461815052031/db658a62203b46baa2f2c660c8a8fdd3-Systematic-Evaluation-Dashboard.html](stitch-downloads/3023668461815052031/db658a62203b46baa2f2c660c8a8fdd3-Systematic-Evaluation-Dashboard.html) (Production Eval Framework).
- **Goal**: Add **POST /evals/run** (trigger run, optional category) and **GET /evals/results** (latest or by id) and **GET /evals/cases** (list cases). Wire Stitch Eval Dashboard; optionally replace Streamlit eval view.

---

## 1. Backend: Eval endpoints

- **GET /evals/cases**: Returns list of eval cases (id, category, input, description, expected_tool_calls, etc.) from [evals/eval_cases/](evals/eval_cases/) or from run_evals. Read from JSON or module.
- **POST /evals/run**: Body optional: `category` (e.g. "mvp") or "all". Runs [evals/run_evals.py](evals/run_evals.py) logic (subprocess or in-process), stores result (file or in-memory), returns run_id or summary. Async or background job for long runs.
- **GET /evals/results**: Query params: `latest=true` or `run_id=...`. Returns report shape: pass_rate, failed/passed counts, category_summary, results array (per-case). Serve from saved report or in-memory.
- **Tests**: Test GET /evals/cases structure; POST /evals/run returns 202 or 200 with run info; GET /evals/results returns report shape.

---

## 2. Frontend: Eval Dashboard screen

- **Stitch reference**: [db658a62203b46baa2f2c660c8a8fdd3-Systematic-Evaluation-Dashboard.html](stitch-downloads/3023668461815052031/db658a62203b46baa2f2c660c8a8fdd3-Systematic-Evaluation-Dashboard.html) — KPI cards (Eval Pass Rate, Hallucination Rate, Multi-step Latency), Run All Tests, Export Report, filters and results table.
- **Wire**: On load, GET /evals/results?latest=true (and optionally GET /evals/cases) to show last run and case list. Run All → POST /evals/run → poll or redirect to results. Export Report → download report JSON or use GET /evals/results.
- **Navigation**: Evaluations is Page 6 in shared Integrator nav.

---

## 3. Data flow

- Page load → GET /evals/results (latest), GET /evals/cases → render KPIs and table.
- User clicks Run All → POST /evals/run → on completion, GET /evals/results with new run_id or latest.
- Export → GET /evals/results (or blob) as download.

---

## 4. Files to touch

| Area | File | Change |
|------|------|--------|
| Backend | [src/api/routes.py](src/api/routes.py) | Add GET /evals/cases, POST /evals/run, GET /evals/results. Invoke evals runner (subprocess or import run_evals). Store result in file or memory. |
| Evals | [evals/run_evals.py](evals/run_evals.py) | Optional: expose function callable from API; or keep subprocess. |
| Tests | [tests/test_api/test_routes.py](tests/test_api/test_routes.py) | Test eval endpoints (mock long-running run if needed). |
| Frontend | `frontend/` (Evaluations page) | Add Eval Dashboard HTML from Stitch; JS to fetch /evals/cases and /evals/results; wire Run All and Export. |

---

## 5. Out of scope

- Adding new eval cases from UI (cases stay in repo).
- Real-time progress stream for run (polling is enough for MVP).
- Other pages.

---

## 6. Implementation order

1. Backend: Add GET /evals/cases (read from evals JSON/module), POST /evals/run (invoke runner, store result), GET /evals/results (serve stored report).
2. Tests: Add route tests for eval endpoints.
3. Frontend: Add Evaluations page from Stitch; wire to eval endpoints; Run All and Export Report.
