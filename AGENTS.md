# AGENTS.md

## Cursor Cloud specific instructions

### Architecture

Ghostfolio Agent is a single-repo Python project with two entry points:

- **FastAPI backend** (port 8000): REST API at `src/api/routes.py` — run with `uvicorn src.api.routes:app --reload`
- **Streamlit frontend** (port 8501): Chat UI at `app/streamlit_app.py` — run with `streamlit run app/streamlit_app.py --server.headless true`

These are independent processes. The Streamlit app calls the agent directly (not through the API).

### Running without external services

Set `USE_MOCK_DATA=true` and `LANGSMITH_TRACING=false` as environment variables to run entirely offline (no Ghostfolio instance or LangSmith needed). The `OPENAI_API_KEY` secret is still required for the LLM agent to produce real chat responses.

### Development commands

Standard commands are documented in `README.md` and `pyproject.toml`. Key references:

- **Install**: `pip install -e ".[dev]"` (inside `.venv`)
- **Lint**: `ruff check .`, `black --check .`, `mypy src/`
- **Test**: `pytest` (runs with coverage by default via `pyproject.toml` addopts)
- **Dev server**: `uvicorn src.api.routes:app --reload --host 0.0.0.0 --port 8000`

### Gotchas

- The `Settings` class in `src/utils/config.py` uses `@lru_cache`, so changing `.env` requires restarting the server (not picked up by hot reload).
- Tests use `asyncio_mode = "auto"` and do not require `OPENAI_API_KEY` — all LLM calls are mocked.
- There are 5 pre-existing test failures in `tests/test_agent/test_core.py` (conversation history and quick method tests). These are known issues in the repo.
- The `requirements.txt` references `langchain-anthropic` and `anthropic`, but `pyproject.toml` uses `langchain-openai` and `openai`. The actual code uses OpenAI (GPT-4o-mini). Install from `pyproject.toml` for dev.
- When the user visits the root URL of the deployed app, they see the FastAPI JSON response — the Streamlit frontend is a separate service on a different port.
