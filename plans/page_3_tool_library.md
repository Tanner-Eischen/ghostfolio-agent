---
name: Page 3 Tool Library
overview: "Implement Page 3 (Tool Library) as an interactive, agent-assisted flow: the bot is open on the page to help the user choose which tools to create; users have no tools when they first start — they create tools with agent guidance. GET/POST /tools; global chat (POST /chat) on page. Assumes Page 1–2 and shared Integrator shell are in place."
todos: []
---

# Page 3: Tool Library (Agent-assisted tool creation)

## Scope and context

- **Focus**: **Interactive and engaging** — Page 3 is where the user **creates** tools with the help of the agent. **When they first start the app, they have no tools**; the Tool Library guides them to define and add tools. The **bot is open on the page** (e.g. chat panel or inline assistant) and helps the user choose which tools would be helpful, suggest names/schemas, and ensure they don’t miss capabilities. Transparent: show what each tool does and why it’s suggested.
- **Existing**: [src/api/routes.py](src/api/routes.py) has `POST /chat` for the agent. Stitch HTML at [5c108504680145159e1660d4c954ef9f-Finance-Tool-Registry-Config.html](stitch-downloads/3023668461815052031/5c108504680145159e1660d4c954ef9f-Finance-Tool-Registry-Config.html) (Financial Tool Library) — use as layout; content is driven by user-created tools.
- **Goal**: **GET /tools** returns the user’s tool registry (empty at first). **POST /tools** creates a new tool (name, description, parameters schema, tags, fact-check enabled). Agent (POST /chat) is available on the page to help users decide what tools to create and fill in schema. Wire Tool Registry UI: list of created tools, “New Tool” flow (optionally with chat), View Logs → LangSmith or GET /traces.

---

## 1. Backend: Tools registry (create + list)

- **GET /tools**: Returns list of tools the user has created: `name`, `description`, `parameters` (JSON schema), `tags`, `fact_check_enabled`. **Initially empty** until user creates tools.
- **POST /tools**: Creates a new tool. Body: `name`, `description`, `parameters` (schema), optional `tags`, `fact_check_enabled`. Persist in file/DB or in-memory registry. Agent runtime can load dynamic tools from this registry (or stub implementations until code is added).
- **Agent on page**: Existing **POST /chat** is used so the bot can help the user (“What do you want your agent to do?” → suggest tools; “Add a portfolio summary tool” → help define name and parameters). Optional: **POST /chat** with context that current page is Tool Library so agent can suggest tool-creation steps.
- **Persistence**: Store created tools (e.g. JSON file or DB) so GET /tools and the agent’s tool set stay in sync. Stub or template implementation for new tools (e.g. placeholder that returns “not implemented”) until user or codegen adds real logic.
- **Tests**: GET /tools returns empty list initially; POST /tools creates entry; GET /tools returns it.

---

## 2. Frontend: Tool Library with bot and creation flow

- **Stitch reference**: [5c108504680145159e1660d4c954ef9f-Finance-Tool-Registry-Config.html](stitch-downloads/3023668461815052031/5c108504680145159e1660d4c954ef9f-Finance-Tool-Registry-Config.html) — Tool Library layout with “New Tool” button, cards area, filters, View Logs.
- **Bot open on page**: Chat panel or inline assistant that calls **POST /chat**. Messaging is contextual: “You don’t have any tools yet. What should your agent be able to do?” or “I suggest adding a portfolio_analysis tool. Here’s a schema…” User can type and get suggestions; then create tool via form or guided flow.
- **Wire**: On load, **GET /tools** → render cards (or empty state: “No tools yet — create one or ask the assistant”). “New Tool” opens a form or wizard; optional: prefill from chat suggestion. Submit → **POST /tools**. View Logs → LangSmith or Observability (GET /traces).
- **Navigation**: Tool Library is Page 3 in shared Integrator nav.

---

## 3. Data flow

- Page load → GET /tools → show list (or empty state). Bot visible; user can ask “What tools should I add?”
- User chats → POST /chat → agent suggests tools; user clicks “Create tool” or fills form → POST /tools → new tool appears in list.
- View Logs → LangSmith or Observability page.

---

## 4. Files to touch

| Area | File | Change |
|------|------|--------|
| Backend | [src/api/routes.py](src/api/routes.py) | Add GET /tools (list user-created tools), POST /tools (create tool with schema). Persist registry (file/DB). Optional: agent loads dynamic tools from registry or stub. |
| Backend | [src/tools/](src/tools/) or registry | Tool registry that stores user-created tools; agent can expose them or stub implementations. |
| Tests | [tests/test_api/test_routes.py](tests/test_api/test_routes.py) | Test GET /tools (empty then with items), POST /tools. |
| Frontend | `frontend/` (Tool Library page) | Tool Library layout + chat panel (POST /chat); GET /tools for list/empty state; “New Tool” flow → POST /tools; View Logs link. |

---

## 5. Out of scope

- Full codegen of tool implementation from schema (stub or template only for MVP).
- Editing/deleting tools from UI (can add later).
- Import Schema from file — placeholder or later.
- Full trace UI (Page 5).

---

## 6. Implementation order

1. Backend: Add GET /tools (persisted registry, empty by default), POST /tools (create and persist); wire agent to use registry or stubs.
2. Tests: Add route tests for GET/POST /tools.
3. Frontend: Add Tool Library page with bot (POST /chat) and tool list (GET /tools); empty state + “New Tool” flow (POST /tools); View Logs link.
