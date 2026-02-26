# Agent Framework – Page Plans

Plans for each of the seven Stitch screens. Page 1 lives in Cursor’s plan store; Pages 2–7 are in this folder.

| Page | Plan file | Stitch HTML (in stitch-downloads/3023668461815052031/) | Main backend |
|------|-----------|--------------------------------------------------------|--------------|
| 1 – Dashboard / Repo | (see [.cursor/plans](.cursor/plans) or project plan) | code.html | GET /repo, /health |
| 2 – Strategy | [page_2_strategy.md](page_2_strategy.md) | 5060997631a5485e9bd267bf6e4bb240-Agent-Strategy-Framework-Selection.html | GET/POST /strategy, /presets later |
| 3 – Tool Library | [page_3_tool_library.md](page_3_tool_library.md) | 5c108504680145159e1660d4c954ef9f-Finance-Tool-Registry-Config.html | GET /tools, link to /traces |
| 4 – Verification | [page_4_verification.md](page_4_verification.md) | 73120773ba8b4cf49ff208d0336b7934-Verification-Layer-HITL-Config.html | GET/PUT /verification/config |
| 5 – Observability | [page_5_observability.md](page_5_observability.md) | eacf252cf36f4314a46c709a638cfd00-Agent-Trace-Observability-Deep-Dive.html | GET /traces, GET /traces/{id} |
| 6 – Evaluations | [page_6_evaluations.md](page_6_evaluations.md) | db658a62203b46baa2f2c660c8a8fdd3-Systematic-Evaluation-Dashboard.html | POST /evals/run, GET /evals/results, GET /evals/cases |
| 7 – Finances | [page_7_finances.md](page_7_finances.md) | cf74bdd6674242e6bddca16e28b5ceb2-AI-Unit-Economics-Cost-Projections.html | GET /finances/usage, GET/POST /finances/projections |

Each plan includes: scope, backend endpoints, frontend wiring to Stitch HTML, data flow, files to touch, out of scope, and implementation order.
