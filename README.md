# Ghostfolio Agent

[![CI](https://github.com/Tanner-Eischen/ghostfolio-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Tanner-Eischen/ghostfolio-agent/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Ghostfolio Agent is a portfolio-analysis assistant built around typed tools and response checks. It can summarize holdings, assess concentration risk, retrieve market data, categorize transactions, and run compliance rules. The repository contains a FastAPI service and a React application.

The previous Railway deployment has been removed. Follow [the deployment guide](docs/DEPLOYMENT.md) to create a new instance.

## What it includes

- Seven LangChain tools for portfolio analysis, risk, market data, transaction categorization, compliance, price history, and cryptocurrency trends
- A verification pipeline with confidence scores, constraint checks, fact checks, and escalation signals
- Evaluation cases for normal, edge, and adversarial requests
- Session history, usage tracking, feedback records, and optional LangSmith traces
- A React interface for portfolio chat, repository analysis, tool management, evaluations, and cost review

## Architecture

```text
React application
      |
      | /api/*
      v
FastAPI service
      |
      +-- Ghostfolio client
      +-- market-data clients
      +-- LangGraph agent and tools
      +-- verification and evaluations
```

The frontend sends `/api/*` requests to Nginx. Nginx reads `BACKEND_URL` when the container starts and proxies those requests to FastAPI.

## Run with Docker

Requirements: Docker and Docker Compose.

```bash
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`. Leave `USE_MOCK_DATA=true` if you do not have a Ghostfolio instance.

```bash
docker compose up --build
```

Open:

- React application: `http://localhost:3000`
- FastAPI documentation: `http://localhost:8000/docs`
- Backend health check: `http://localhost:8000/health`

## Run without Docker

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn src.api.routes:app --reload --port 8002
```

On Windows, activate the environment with `.venv\Scripts\activate`.

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://localhost:8002`.

## Connect Ghostfolio

Set these variables in `.env`:

```dotenv
USE_MOCK_DATA=false
GHOSTFOLIO_API_URL=http://localhost:3333
GHOSTFOLIO_ACCESS_TOKEN=replace_with_your_token
```

Create the access token in Ghostfolio under **Settings > Security**. Keep the token on the backend. Do not put it in the React application or commit it to Git.

## Main API routes

| Route | Purpose |
| --- | --- |
| `GET /health` | Service and dependency status |
| `POST /chat` | Run an agent request |
| `GET /portfolio` | Portfolio summary |
| `GET /portfolio/risk` | Concentration and risk analysis |
| `GET /market/{symbol}` | Market-data lookup |
| `GET /tools` | Available tools |
| `POST /evals/run` | Run evaluation cases |
| `GET /traces` | Stored trace records |

See the interactive FastAPI documentation at `/docs` for the full API.

## Test and build

Backend:

```bash
python -m pytest -q
python -m ruff check src tests --select E9,F63,F7,F82
```

Frontend:

```bash
cd frontend
npm ci
npm audit --omit=dev --audit-level=high
npm run lint
npm run build
```

The CI workflow runs these checks and builds both Docker images.

## Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Yes | Model requests |
| `USE_MOCK_DATA` | No | Use local sample portfolio data |
| `GHOSTFOLIO_API_URL` | For live data | Ghostfolio server URL |
| `GHOSTFOLIO_ACCESS_TOKEN` | For live data | Server-side Ghostfolio token |
| `LANGSMITH_API_KEY` | No | LangSmith traces |
| `COINGECKO_API_KEY` | No | Higher CoinGecko rate limits |
| `SECRET_KEY` | Production | Application secret |
| `CORS_ORIGINS` | Production | Comma-separated frontend origins |
| `BACKEND_URL` | Frontend container | FastAPI URL used by Nginx |

The complete list and local defaults are in [.env.example](.env.example).

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the two-service Railway configuration and post-deployment checks.

## License

MIT. See [LICENSE](LICENSE).
