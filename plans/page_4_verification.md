---
name: Page 4 Verification
overview: "Implement Page 4 (Verification / HITL): add verification config endpoint (read/write), wire the Stitch Verification screen (fact-checking, hallucination detection, confidence scoring, HITL triggers). Assumes Page 1–3 and shared Integrator shell are in place."
todos: []
---

# Page 4: Verification (High-Stakes / HITL)

## Scope and context

- **Focus**: Configure automated verification layers and Human-in-the-Loop triggers — fact-checking, hallucination detection, confidence scoring, escalation rules. Universal verification config; finance-specific rules can live in backend logic.
- **Existing**: [src/verification/](src/verification/) pipeline (fact_checker, confidence, escalation). Stitch HTML at [stitch-downloads/3023668461815052031/73120773ba8b4cf49ff208d0336b7934-Verification-Layer-HITL-Config.html](stitch-downloads/3023668461815052031/73120773ba8b4cf49ff208d0336b7934-Verification-Layer-HITL-Config.html) (High-Stakes Verification, Step 5 of 6).
- **Goal**: Add **GET/PUT /verification/config** (or **/config/verification**) for toggles and thresholds. Wire Stitch Verification screen to it.

---

## 1. Backend: Verification config endpoint

- **Endpoints**: `GET /verification/config` returns current config; `PUT /verification/config` (or `POST`) accepts and persists config.
- **Config shape**: e.g. `fact_checking_enabled`, `hallucination_detection_enabled`, `confidence_scoring_enabled`, `confidence_threshold`, `escalation_threshold`, `hitl_triggers` (list or object). Match toggles and sliders on Stitch screen.
- **Persistence**: In-memory or file/DB; agent or verification pipeline reads config at runtime (or on next request). Optional: merge into /strategy config.
- **Tests**: Test GET structure; PUT updates and GET reflects it.

---

## 2. Frontend: Verification screen

- **Stitch reference**: [73120773ba8b4cf49ff208d0336b7934-Verification-Layer-HITL-Config.html](stitch-downloads/3023668461815052031/73120773ba8b4cf49ff208d0336b7934-Verification-Layer-HITL-Config.html) — Automated Verification Layers (Fact Checking, Hallucination Detection, Confidence Scoring), HITL triggers, Load Preset, Save Configuration.
- **Wire**: On load, GET /verification/config and set toggles/sliders; on Save, PUT /verification/config with form data.
- **Navigation**: Verification is Page 4 in shared Integrator nav.

---

## 3. Data flow

- Page load → GET /verification/config → populate toggles and thresholds.
- User edits and clicks Save → PUT /verification/config → confirm.

---

## 4. Files to touch

| Area | File | Change |
|------|------|--------|
| Backend | [src/api/routes.py](src/api/routes.py) | Add `VerificationConfigResponse` / `VerificationConfigRequest`; GET/PUT /verification/config. Optional: [src/verification/](src/verification/) reads config from settings or passed into pipeline. |
| Config | [src/utils/config.py](src/utils/config.py) | Optional: add verification-related env defaults. |
| Tests | [tests/test_api/test_routes.py](tests/test_api/test_routes.py) | Test GET/PUT /verification/config. |
| Frontend | `frontend/` (Verification page) | Add Verification HTML from Stitch; JS to fetch/submit /verification/config. |

---

## 5. Out of scope

- Changing verification pipeline logic (only config surface); pipeline already exists.
- Presets for verification (can reuse /presets later).
- Other pages.

---

## 6. Implementation order

1. Backend: Add Pydantic models and GET/PUT /verification/config; minimal persistence; optional wiring to verification pipeline.
2. Tests: Add route tests for /verification/config.
3. Frontend: Add Verification page from Stitch; wire to GET/PUT /verification/config.
