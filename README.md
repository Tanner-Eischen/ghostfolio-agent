# Ghostfolio Agent

An AI-powered portfolio assistant that sits on top of [Ghostfolio](https://ghostfol.io/), providing natural language access to portfolio analysis, risk assessment, and financial insights.

## What is Ghostfolio?

[Ghostfolio](https://ghostfol.io/) is a modern, open-source wealth management application that helps you track and analyze your investment portfolio. It offers both:
- **Ghostfolio Cloud** - A hosted premium service at ghostfol.io
- **Self-hosted** - Run your own instance via Docker

Ghostfolio Agent enhances your Ghostfolio experience by adding an AI assistant that understands your portfolio and can answer questions in natural language.

## Features

- **Natural Language Portfolio Queries** - Ask questions like "What's my portfolio worth?" or "How diversified am I?"
- **Risk Assessment** - Analyze your portfolio's risk exposure and concentration
- **Market Data Lookup** - Look up current prices and asset information (Yahoo Finance, CoinGecko)
- **Transaction Categorization** - Automatically categorize transaction types
- **Compliance Checking** - Verify portfolio allocations against constraints
- **Price History** - View historical price data for assets
- **Trending Crypto** - Get trending cryptocurrency information
- **Conversation Memory** - Maintains context across multiple queries
- **Verification Pipeline** - Built-in confidence scoring and fact-checking

## Quick Start

### Option A: Use the Hosted App (No Install)

1. **Get a Ghostfolio access token**
   - **Ghostfolio Cloud users:** Go to Settings > Security, create an access token
   - **Self-hosted:** Run Ghostfolio locally, then Settings > Security > create token

2. **Open the app** at [ghostfolio-agent-production-e24d.up.railway.app](https://ghostfolio-agent-production-e24d.up.railway.app)

3. **Connect Ghostfolio** - Click your avatar (top right) > Connect Ghostfolio, paste your token and optionally your instance URL

4. **Start chatting** - Ask "What's my portfolio worth?" or "Am I diversified?"

### Option B: Run Locally

**Prerequisites:** Python 3.11+, Node.js 18+, Git

```bash
# Clone and setup
git clone https://github.com/Tanner-Eischen/ghostfolio-agent.git
cd ghostfolio-agent
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Run backend (terminal 1)
uvicorn src.api.routes:app --reload --port 8002

# Run frontend (terminal 2)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 and connect your Ghostfolio account.

## Connecting Your Ghostfolio Account

### Ghostfolio Cloud (Premium Users)
1. Log in to ghostfol.io
2. Go to Settings > Security
3. Generate an access token
4. In Ghostfolio Agent: avatar > Connect Ghostfolio > paste token (leave URL as default)

### Self-Hosted Ghostfolio
1. Run Ghostfolio (e.g., via Docker at localhost:3333)
2. Go to Settings > Security > generate token
3. In Ghostfolio Agent: avatar > Connect Ghostfolio > enter your URL + paste token

> **Note:** If using the hosted app with a local Ghostfolio, you'll need to expose your local instance (e.g., via ngrok) since the hosted server cannot reach localhost.

### Importing sample data (Ghostfolio CSV)

To load sample activities into Ghostfolio via its built-in import:

1. In Ghostfolio, go to **Activities** (or **Portfolio** → **Activities**) and use **Import**.
2. Use the sample CSV in this repo: **`data/ghostfolio_sample_import.csv`**.

The CSV uses Ghostfolio’s expected columns: **Date**, **Symbol**, **Type**, **Quantity**, **unitPrice**, **Currency**, **fee** (camelCase for unitPrice and fee to match the API). Types include BUY, SELL, DIVIDEND. Dates are `YYYY-MM-DD`, currency USD; numeric fields use decimals (e.g. 225.00, 0.00).

Alternatively, run `python scripts/populate_ghostfolio_local.py` to create the same sample activities via the API (requires `GHOSTFOLIO_API_URL` and `GHOSTFOLIO_ACCESS_TOKEN` in `.env`).

## Demo Mode (No Credentials Required)

Run the app with mock portfolio data:

```bash
# Set environment and run
USE_MOCK_DATA=true uvicorn src.api.app:app --port 8002

# Or in .env
USE_MOCK_DATA=true
```

**Included Mock Data:**
- $150,000 USD portfolio
- Holdings: AAPL, MSFT, VTI, BTC, BND, NVDA
- YTD Performance: +9.09%

## Quick Demo (No API Keys Required)

Clone and run with mock data:

```bash
git clone https://github.com/Tanner-Eischen/ghostfolio-agent.git
cd ghostfolio-agent
docker build -t ghostfolio-agent .
docker run -e USE_MOCK_DATA=true -p 8000:8000 ghostfolio-agent
```

Open http://localhost:8000 and try the preset prompts.

## Example Queries

- "What's my portfolio worth?"
- "Show me my top 5 holdings"
- "How diversified is my portfolio?"
- "What's my risk level?"
- "Show me my recent transactions"
- "What's the price of AAPL?"
- "What crypto do I own?"

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│                 Vite + TypeScript + Tailwind             │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 Backend (FastAPI)                        │
│   REST API + Session Management + Verification          │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌─────────────────────┐       ┌─────────────────────────┐
│   Ghostfolio API    │       │    AI Agent (LangGraph) │
│   (Cloud or Local)  │       │    + LangChain Tools    │
└─────────────────────┘       └─────────────────────────┘
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check and dependency status |
| `POST /chat` | Send a message to the agent |
| `GET /portfolio` | Quick portfolio summary |
| `GET /sessions` | List conversation sessions |
| `DELETE /sessions/{id}` | Clear session history |
| `GET /tools` | List available tools |
| `POST /feedback` | Submit feedback |

Full API docs at `/docs` (Swagger) or `/redoc`.

## Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `GHOSTFOLIO_API_URL` | Ghostfolio instance URL | No (defaults to localhost:3333) |
| `GHOSTFOLIO_ACCESS_TOKEN` | Ghostfolio access token | No (set per-request in app) |
| `LANGSMITH_API_KEY` | LangSmith API key for tracing | No |
| `LANGSMITH_TRACING` | Enable LangSmith tracing | No (default: true) |
| `USE_MOCK_DATA` | Use mock portfolio data | No (default: false) |
| `ENVIRONMENT` | Environment name | No (default: development) |
| `PORT` | Server port | No (default: 8000) |

## Project Structure

```
ghostfolio-agent/
├── src/
│   ├── agent/           # LangGraph agent implementation
│   │   ├── core.py      # Main GhostfolioAgent class
│   │   ├── prompts.py   # System prompts
│   │   └── state.py     # Agent state definitions
│   ├── api/
│   │   ├── ghostfolio.py    # Ghostfolio API client
│   │   └── routes.py        # FastAPI routes
│   ├── tools/           # LangChain tools
│   │   ├── portfolio_analysis.py
│   │   ├── risk_assessment.py
│   │   ├── market_data_lookup.py
│   │   └── ...
│   ├── utils/           # Utilities (config, logging, caching)
│   └── verification/    # Response verification pipeline
├── frontend/            # React frontend
│   └── src/
│       ├── components/  # React components
│       ├── pages/       # Page components
│       └── api/         # API client
├── tests/               # Test suite
└── evals/               # Evaluation framework
```

## Tools

| Tool | Description |
|------|-------------|
| `portfolio_analysis` | Analyze portfolio value, holdings, allocation, performance |
| `risk_assessment` | Evaluate diversification, concentration, volatility |
| `market_data_lookup` | Fetch current prices from Yahoo Finance/CoinGecko |
| `transaction_categorize` | Categorize transaction types |
| `compliance_check` | Check portfolio compliance against constraints |
| `price_history` | Get historical price data |
| `trending_crypto` | Get trending cryptocurrency data |

## Core Workflows

### 1. Portfolio Overview
> "What's my portfolio worth?"

Get total value, holdings breakdown, and performance metrics.

### 2. Risk Analysis
> "How diversified am I?"

Analyze allocation, concentration risk, and diversification score.

### 3. Market Data Lookup
> "What's the price of AAPL?"

Fetch current prices from Yahoo Finance and CoinGecko.

### 4. Transaction History
> "Show me my recent transactions"

View categorized transaction history.

## Test Coverage

| Module | Coverage |
|--------|----------|
| `src/api/` | 85% |
| `src/agent/` | 90% |
| `src/tools/` | 88% |
| `src/verification/` | 92% |
| **Overall** | **88%** |

Run tests with coverage:
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Evaluation Results

| Category | Pass Rate |
|----------|-----------|
| Tool Selection | 86% |
| Multi-Step | 100% |
| Correctness | 60% |
| Tool Execution | 90% |
| Overall | **81%** |

Based on 75 test cases. Full results in `evals/results/`.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run evaluations
python evals/run_evals.py --validate
python evals/run_evals.py --category mvp --save

# Format and lint
black src tests
ruff check src tests
mypy src
```

## Deployment

### Docker (Primary)

Build and run with mock data for demos:
```bash
docker build -t ghostfolio-agent .
docker run -e USE_MOCK_DATA=true -p 8000:8000 ghostfolio-agent
```

### With Real Ghostfolio Data

```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your-key \
  -e GHOSTFOLIO_API_URL=your-instance \
  -e GHOSTFOLIO_ACCESS_TOKEN=your-token \
  ghostfolio-agent
```

### Railway (Cloud)

See `railway.backend.toml` and `frontend/railway.toml` for Railway deployment.

To deploy your own:
1. Fork the repository
2. Create a Railway project and connect your repo
3. Set environment variables (`OPENAI_API_KEY`, `SECRET_KEY`)
4. Deploy

## Tech Stack

**Backend:**
- Python 3.11+
- FastAPI
- LangChain & LangGraph
- OpenAI GPT-4o-mini
- Pydantic

**Frontend:**
- React 19
- TypeScript
- Vite
- Tailwind CSS

**Infrastructure:**
- Docker
- Railway
- LangSmith (tracing)

## Cost Analysis

Running this agent requires:
- **OpenAI API costs** - ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens (GPT-4o-mini)
- **Hosting** - Railway starter plan (~$5/month)

Estimated monthly cost for moderate usage (10 queries/user/day):
- 100 users: ~$2/month
- 1,000 users: ~$20/month

Use the Observability & Cost page in the app to monitor usage.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Ghostfolio](https://ghostfol.io/) - The wealth management platform this agent extends
- [LangChain](https://langchain.com/) - Agent framework
- [OpenAI](https://openai.com/) - Language models
