---
name: Page 7 Finances
overview: "Implement Page 7 (Finances / AI Unit Economics): add usage and cost-projection endpoints, wire the Stitch Cost Projections UI (dev spend, production projections, cost per query). Assumes Page 1–6 and shared Integrator shell are in place."
todos: []
---

# Page 7: Finances (AI Unit Economics & Cost Projections)

## Scope and context

- **Focus**: Track development spend and simulate production costs — API cost, token usage, cost per query; sliders for users/queries to project scale. Universal cost tracking; domain doesn’t change structure.
- **Existing**: LangSmith and OpenAI report token usage; no cost aggregation in repo yet. Stitch HTML at [stitch-downloads/3023668461815052031/cf74bdd6674242e6bddca16e28b5ceb2-AI-Unit-Economics-Cost-Projections.html](stitch-downloads/3023668461815052031/cf74bdd6674242e6bddca16e28b5ceb2-AI-Unit-Economics-Cost-Projections.html) (AI Unit Economics & Cost Projections).
- **Goal**: Add **GET /finances/usage** (or **GET /costs/usage**) — current/total API cost, token counts, optional breakdown. Add **GET /finances/projections** (or **GET /costs/projections**) — query params e.g. `users`, `queries_per_user` (or pass in body) and return projected cost. Wire Stitch Cost Projections UI.

---

## 1. Backend: Usage and projections endpoints

- **GET /finances/usage** (or GET /costs/usage): Returns e.g. `total_api_cost`, `total_input_tokens`, `total_output_tokens`, `period` (e.g. "current_month"), optional `breakdown` by model or source. Data from LangSmith usage API, or from app-level aggregation (store token/cost per request), or mock for MVP.
- **GET /finances/projections** (or POST with body): Params e.g. `users`, `queries_per_user`, `avg_tokens_per_query`. Returns e.g. `projected_monthly_cost`, `cost_per_query`, `cost_per_user`. Use current unit cost (from usage or config) and simple math.
- **Persistence**: If not using LangSmith usage API, persist token/cost per run in memory or file/DB and aggregate. Optional: env for price per 1K tokens (OpenAI, etc.).
- **Tests**: Test GET /finances/usage structure; GET (or POST) /finances/projections with params returns numbers.

---

## 2. Frontend: Cost Projections screen

- **Stitch reference**: [cf74bdd6674242e6bddca16e28b5ceb2-AI-Unit-Economics-Cost-Projections.html](stitch-downloads/3023668461815052031/cf74bdd6674242e6bddca16e28b5ceb2-AI-Unit-Economics-Cost-Projections.html) — Current Development Spend (Total API Cost, etc.), Production Projections (sliders for volume), cost per query.
- **Wire**: On load, GET /finances/usage and fill "Current Development Spend" cards. Sliders for users/queries → GET /finances/projections?users=…&queries_per_user=… (or POST) and update projected cost and cost per query.
- **Navigation**: Finances is Page 7 in shared Integrator nav.

---

## 3. Data flow

- Page load → GET /finances/usage → render spend cards.
- User changes sliders → GET /finances/projections (or POST) with params → render projected cost and per-query cost.

---

## 4. Files to touch

| Area | File | Change |
|------|------|--------|
| Backend | [src/api/routes.py](src/api/routes.py) | Add GET /finances/usage, GET or POST /finances/projections. Optional: [src/utils/usage_aggregator.py](src/utils/usage_aggregator.py) or LangSmith client for usage. |
| Config | [src/utils/config.py](src/utils/config.py) | Optional: price per token or per 1K tokens for projections. |
| Tests | [tests/test_api/test_routes.py](tests/test_api/test_routes.py) | Test /finances/usage and /finances/projections. |
| Frontend | `frontend/` (Finances page) | Add Cost Projections HTML from Stitch; JS to fetch usage and projections; wire sliders. |

---

## 5. Out of scope

- Historical time-series (only current/latest for MVP).
- Billing integration; use aggregated usage and fixed price config.
- Other pages.

---

## 6. Implementation order

1. Backend: Add GET /finances/usage (LangSmith or aggregated store), GET or POST /finances/projections with simple formula.
2. Tests: Add route tests for finances endpoints.
3. Frontend: Add Finances page from Stitch; wire usage and projections; wire sliders to projections request.
