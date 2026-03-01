# Ghostfolio Agent

> AI-powered portfolio assistant for [Ghostfolio](https://ghostfol.io) - Analyze, categorize, and assess risk with natural language

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Deployed on Railway](https://img.shields.io/badge/deployed-railway-purple)](https://ghostfolio-agent-production-e24d.up.railway.app)

**Live Demo:** https://ghostfolio-agent-production-e24d.up.railway.app

When offered as a hosted service, end users only need their Ghostfolio access key; the service provider fronts the compute and uses the in-app Observability & Cost page to track usage and projections.

## For people using the service

If you're using a hosted instance of Ghostfolio Agent (e.g. the live demo above), the only thing you need is a **Ghostfolio access token** to connect your portfolio:

1. **Get your token:** In [Ghostfolio](https://ghostfolio.io), go to **Settings → Security** and create an access token.
2. **Use the app:** Open the service URL; the administrator of your instance configures the Ghostfolio connection. (Per-user "connect your own Ghostfolio account" with your key may be available in a future release.)

You do not need to install anything, set API keys, or run servers.

## Features

- **Portfolio Analysis** - Get insights on holdings, allocation, and performance
- **Risk Assessment** - Evaluate diversification and concentration risk
- **Market Data Lookup** - Fetch current prices for stocks, ETFs, and crypto
- **Verification Layer** - Confidence scoring, escalation signals, and domain checks
- **MVP Eval Framework** - Atomic, objective pass/fail evals with Streamlit visualization

## Quick Start

### Using the hosted app

Go to the [live demo](https://ghostfolio-agent-production-e24d.up.railway.app). All you need is your **Ghostfolio access token** (see [For people using the service](#for-people-using-the-service) above for how to get it). No install or API keys required.

### For service providers / self-hosting

If you run the Ghostfolio Agent (your own deployment or local), you set the environment variables and run the backend and frontend. End users of your deployment do not set these; they only need their Ghostfolio access token.

#### Installation

```bash
# Clone the repository
git clone https://github.com/Tanner-Eischen/ghostfolio-agent.git
cd ghostfolio-agent

# Create virtual environment (required: pydantic>=2.10 for config to load; the venv avoids version conflicts)
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

If you see `ImportError: cannot import name 'Secret' from 'pydantic'`, your environment has an old pydantic (e.g. 2.6). Use the project venv and reinstall: `pip install -r requirements.txt` (requirements pin `pydantic>=2.10.0`). On Windows you can run the backend with the venv automatically: `.\scripts\run_backend.ps1`.

#### Requirements

- **Git** – Required for the backend to clone repositories (Repo Connect). Install [Git](https://git-scm.com/) and ensure it is in your PATH. The backend checks Git at startup and reports `dependencies.git` in `/health`.

#### Setup

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Add your API keys to `.env` (required for running the service):
```bash
OPENAI_API_KEY=your_key_here
LANGSMITH_API_KEY=your_key_here
GHOSTFOLIO_ACCESS_TOKEN=your_token_here
```

3. **Local Ghostfolio (real portfolio data):** To connect the agent to your own portfolio instead of mock data:
   - Clone [Ghostfolio](https://github.com/ghostfolio/ghostfolio) and start its server locally (see that repo’s README: usually Postgres + Redis via Docker, then `npm start`).
   - Open http://localhost:3333, create an account, then go to **Settings → Security** and create an access token.
   - Put that token in `GHOSTFOLIO_ACCESS_TOKEN` in this project’s `.env` and set `USE_MOCK_DATA=false`.
   - Keep `GHOSTFOLIO_API_URL=http://localhost:3333` (default).

#### Run the app locally

The app uses a **React (Vite) frontend** that talks to the FastAPI backend. Run both:

**1. Backend (API)** – from the project root:

```bash
# Start the API server (port 8002 so the frontend proxy works)
uvicorn src.api.routes:app --reload --port 8002

# Or use the CLI (set PORT=8002 in .env to match frontend)
ghostfolio-agent
```

**2. Frontend** – in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173**. The Vite dev server proxies `/api` to the backend on port 8002.


## Usage Examples

### Chat with the Agent

```python
from src.agent.core import GhostfolioAgent

agent = GhostfolioAgent()

# Analyze your portfolio
response = await agent.chat("What's my portfolio worth?")
print(response)

# Get risk assessment
response = await agent.chat("Am I diversified enough?")
print(response)

# Market data lookup
response = await agent.chat("Get the latest market data for AAPL and MSFT.")
print(response)
```

### Use Individual Tools

```python
from src.tools import portfolio_analysis, risk_assessment

# Analyze portfolio
analysis = await portfolio_analysis(timeframe="YTD")
print(f"Total Value: ${analysis.total_value}")
print(f"YTD Performance: {analysis.performance.relative_change * 100:.2f}%")

# Assess risk
risk = await risk_assessment()
print(f"Risk Score: {risk.overall_risk_score}/100")
print(f"Recommendations: {risk.recommendations}")
```

## Architecture

```
ghostfolio-agent/
├── src/
│   ├── agent/          # LangChain/LangGraph agent core
│   │   ├── core.py     # Main agent definition
│   │   ├── state.py    # State management
│   │   └── prompts.py  # System prompts
│   ├── tools/          # LangChain tools
│   │   ├── portfolio_analysis.py
│   │   ├── risk_assessment.py
│   │   ├── market_data_lookup.py
│   │   └── __init__.py
│   ├── verification/   # Response verification
│   ├── api/            # API clients & routes
│   └── utils/          # Utilities
├── evals/              # Evaluation framework
├── frontend/           # React (Vite) frontend
├── tests/              # Test suite
└── app/                # Optional Streamlit UI
```

## Tools

| Tool | Description |
|------|-------------|
| `portfolio_analysis` | Analyze holdings, allocation, performance metrics |
| `risk_assessment` | Evaluate diversification, concentration, volatility |
| `market_data_lookup` | Fetch current prices from Yahoo Finance/CoinGecko |

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/Tanner-Eischen/ghostfolio-agent.git
cd ghostfolio-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install development dependencies
pip install -e ".[dev]"
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_tools/test_portfolio_analysis.py
```

### Run Evaluations

```bash
# Validate schema and cases
python evals/run_evals.py --category mvp --validate

# Run MVP evals
python evals/run_evals.py --category mvp

# Run and save report for Streamlit
python evals/run_evals.py --category mvp --save
```

### Eval Schema (MVP)

Each eval case uses an atomic criteria format:

- `id`, `category`, `input`, `description`
- `expected_tool_calls`, `expected_output_fields`
- `criteria[]` where `check_type` is one of:
  - `tool_called`
  - `field_present`

`field_present` passes only when the expected field exists as a top-level key in at least one object inside `tool_outputs`.

## Configuration

The variables below are for **whoever runs the backend** (the service provider). End users of your deployment do not set these.

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` |  API key | Required |
| `LANGCHAIN_API_KEY` | LangSmith API key for tracing | Required for tracing |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith tracing | `true` |
| `LANGCHAIN_PROJECT` | LangSmith project name | `ghostfolio-agent` |
| `GHOSTFOLIO_API_URL` | Ghostfolio instance URL | `http://localhost:3333` |
| `USE_MOCK_DATA` | Use mock data for development | `false` |
| `CACHE_TTL_SECONDS` | Cache TTL for market data | `300` |
| `LOG_LEVEL` | Logging level | `INFO` |

### LangSmith Tracing Setup

The agent automatically integrates with [LangSmith](https://smith.langchain.com/) for observability:

1. **Get your LangSmith API key:**
   - Go to [LangSmith](https://smith.langchain.com/)
   - Create a free account or sign in
   - Go to Settings → API Keys → Create API Key

2. **Add to your `.env` file:**
   ```bash
   LANGSMITH_API_KEY=lsv2_pt_xxxxxxxx
   LANGSMITH_TRACING=true
   LANGSMITH_PROJECT=AgentForge
   ```

3. **View traces:**
   - All agent calls are automatically traced
   - View in LangSmith dashboard under your project
   - Each response includes a `trace_url` for direct access

**What gets traced:**
- Agent conversations (input/output)
- Tool calls and results
- LLM token usage
- Verification pipeline results
- Response confidence scores

**Log user feedback:**
```python
# After a conversation, log feedback
response = await agent.chat_with_context("What's my portfolio worth?", session_id="user-123")
agent.log_user_feedback("user-123", score=1.0, key="thumbs_up")
```

## Evaluation Results

**69 test cases, 100% pass rate**

| Category | Count | Pass Rate |
|----------|-------|-----------|
| Happy Path | 25 | 100% |
| Edge Cases | 17 | 100% |
| Adversarial | 14 | 100% |
| Correctness | 13 | 100% |

```bash
# Run evaluations
python evals/run_evals.py --save --output results.json
```

## AI Cost Analysis (for service providers)

As the service provider, you front the compute (LLM, infrastructure). Use the **Observability & Cost** page in the app to monitor real usage and the projections below to plan costs as you scale users.

### Development Costs
- **LLM:** GPT-4o-mini
- **Total API calls:** ~2,000 during development
- **Total tokens:** ~500K input / ~200K output
- **Estimated spend:** ~$5 USD

### Production Projections (per month)

| Users | Queries/User/Day | Est. Cost/Month |
|-------|------------------|-----------------|
| 100 | 10 | ~$2 |
| 1,000 | 10 | ~$20 |
| 10,000 | 10 | ~$200 |
| 100,000 | 10 | ~$2,000 |

**Assumptions:** 500 input tokens, 200 output tokens per query; GPT-4o-mini pricing. See [docs/COST_ANALYSIS.md](docs/COST_ANALYSIS.md) for detailed breakdowns.

## Tech Stack

- **Agent Framework**: LangChain + LangGraph
- **LLM**: OpenAI GPT-4o-mini (configurable)
- **Observability**: LangSmith
- **Backend**: FastAPI
- **Frontend**: React (Vite)
- **Testing**: pytest, pytest-asyncio (432 tests)

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Ghostfolio](https://ghostfol.io) - Open Source Wealth Management Software
- [LangChain](https://langchain.com) - Agent framework
- [Anthropic](https://anthropic.com) - Claude AI

## Support

- 📖 [Documentation](https://github.com/Tanner-Eischen/ghostfolio-agent#readme)
- 🐛 [Issue Tracker](https://github.com/Tanner-Eischen/ghostfolio-agent/issues)
- 💬 [Discussions](https://github.com/Tanner-Eischen/ghostfolio-agent/discussions)

## Deployment

This project is deployed on Railway. To deploy your own instance (as the service provider):

1. Fork this repository
2. Create a new project on [Railway](https://railway.app)
3. Connect your GitHub repository
4. **Backend and frontend:** Add two services (or one if you only need the API). In each service’s **Settings → Build**, set **Dockerfile path** explicitly: `Dockerfile.backend` for the API, `Dockerfile.frontend` for the frontend. Do not rely on a root `railway.json`—it applies to every service and forces the same Dockerfile (e.g. backend onto the frontend). See `railway.services.toml` for the full setup.
5. Set the required environment variables (see `.env.example`). These are for your backend only; end users of your deployment only need their Ghostfolio access token.
6. Deploy!

Required environment variables (service provider):
- `OPENAI_API_KEY` - Your OpenAI API key
- `SECRET_KEY` - Random string for session encryption
- `LANGSMITH_API_KEY` - For observability (optional)
