# AGENTS.md

## Cursor Cloud specific instructions

### Project Overview

Ghostfolio Agent is an AI-powered portfolio assistant built with FastAPI (backend, port 8000) and Streamlit (frontend, port 8501). It uses LangChain/LangGraph with OpenAI GPT-4o-mini.

### Environment Setup

- Python 3.11+ required (3.12 works fine). The venv lives at `.venv/`.
- Install dev dependencies: `source .venv/bin/activate && pip install -e ".[dev]"`
- A `.env` file is needed at root. Copy from `.env.example` and set `USE_MOCK_DATA=true` for offline development. Set `LANGSMITH_TRACING=false` to disable tracing if no LangSmith key is available.

### Running Services

- **FastAPI backend**: `source .venv/bin/activate && USE_MOCK_DATA=true uvicorn src.api.routes:app --reload --port 8000`
- **Streamlit frontend**: `source .venv/bin/activate && USE_MOCK_DATA=true streamlit run app/streamlit_app.py --server.port 8501 --server.headless true`
- Health check: `curl http://localhost:8000/health`

### Lint / Test / Build

- **Lint**: `ruff check .` — pre-existing lint issues exist (115 warnings, mostly import sorting); the codebase has not been fully formatted.
- **Format check**: `black --check .` — 33 files have pre-existing formatting differences.
- **Type check**: `mypy src/`
- **Tests**: `pytest` — 427/432 pass; 5 pre-existing failures in `tests/test_agent/test_core.py` (test methods like `test_analyze_portfolio` reference methods not present on `GhostfolioAgent`).
- **Coverage**: ~81% via `pytest --cov=src`.

### Key Gotchas

- The codebase uses `langchain-openai` / `ChatOpenAI` (GPT-4o-mini) despite README and `.env.example` mentioning Anthropic/Claude. The actual LLM provider is OpenAI. `OPENAI_API_KEY` is required for real agent interaction; mock data mode bypasses LLM calls in tools but the agent's chat still needs an LLM.
- `requirements.txt` lists `langchain-anthropic` / `anthropic` while `pyproject.toml` lists `langchain-openai` / `openai`. Use `pip install -e ".[dev]"` (from `pyproject.toml`) for the correct dependencies.
- `python3.12-venv` system package may need to be installed (`sudo apt-get install python3.12-venv`) before creating the venv.
- The `conftest.py` references a `langchain_api_key` setting field that doesn't exist in the current `Settings` model — this is harmless because `pydantic-settings` has `extra="ignore"`.
