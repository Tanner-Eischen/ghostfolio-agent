# Ghostfolio Agent

An AI-powered portfolio assistant that lets you query your investments in plain English. Built on top of [Ghostfolio](https://ghostfol.io/).

## Try It Now

**Live Demo:** [ghostfolio-frontend-production.up.railway.app](https://ghostfolio-frontend-production.up.railway.app)

The demo includes sample portfolio data - no account needed. Just open the link and start asking questions.

### Sample Prompts to Try

| Prompt | What You'll See |
|--------|-----------------|
| "What's my portfolio worth?" | Total value with currency breakdown |
| "How diversified am I?" | Diversification score and concentration analysis |
| "What's my risk level?" | Risk assessment with asset allocation |
| "Show me my top holdings" | Top 5 positions with values |
| "What's the price of AAPL?" | Real-time price lookup |
| "What crypto do I own?" | Crypto holdings breakdown |


## Quick Start

### Option 1: Use the Hosted Demo (Recommended)

1. Open the live demo
2. Start chatting with the sample portfolio
3. (Optional) Connect your own Ghostfolio account via the avatar menu

### Option 2: Run Locally

```bash
# Clone and setup
git clone https://github.com/Tanner-Eischen/ghostfolio-agent.git
cd ghostfolio-agent
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run with demo data (no API keys needed)
USE_MOCK_DATA=true uvicorn src.api.app:app --port 8002

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 and start chatting.

### Option 3: Docker

```bash
docker build -t ghostfolio-agent .
docker run -e USE_MOCK_DATA=true -p 8000:8000 ghostfolio-agent
```

## Connecting Your Ghostfolio Account

To use your real portfolio data:

### Ghostfolio Cloud (Premium Users)
1. Log in to [ghostfol.io](https://ghostfol.io)
2. Go to **Settings → Security**
3. Generate an access token
4. In Ghostfolio Agent: click avatar → Connect Ghostfolio → paste token

### Self-Hosted Ghostfolio
1. Run Ghostfolio locally (e.g., via Docker at `localhost:3333`)
2. Go to **Settings → Security** → generate token
3. In Ghostfolio Agent: enter your local URL + paste token

> **Note:** If using the hosted app with a local Ghostfolio, you'll need to expose your instance (e.g., via ngrok) since the hosted server cannot reach localhost.

## Features

- **Natural Language Queries** - Ask questions in plain English
- **Risk Assessment** - Analyze portfolio risk and concentration
- **Market Data** - Real-time prices from Yahoo Finance and CoinGecko
- **Verification Pipeline** - Built-in confidence scoring for responses
- **Conversation Memory** - Context persists across messages

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

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check and mock mode status |
| `POST /chat` | Send a message to the agent |
| `GET /portfolio` | Quick portfolio summary |
| `GET /tools` | List available tools |

Full API docs at `/docs` (Swagger) when running locally.

## Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | For real AI responses |
| `USE_MOCK_DATA` | Use sample portfolio data | No (default: false) |
| `GHOSTFOLIO_API_URL` | Ghostfolio instance URL | No (defaults to ghostfol.io) |
| `GHOSTFOLIO_ACCESS_TOKEN` | Ghostfolio access token | No (set in app) |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=src

# Format and lint
black src tests
ruff check src tests
```

## Test Coverage

| Module | Coverage |
|--------|----------|
| `src/api/` | 85% |
| `src/agent/` | 90% |
| `src/tools/` | 88% |
| `src/verification/` | 92% |
| **Overall** | **88%** |

## Deployment

### Railway

The app is deployed on Railway. To deploy your own:

1. Fork this repository
2. Create a Railway project and connect your fork
3. Set environment variables (`OPENAI_API_KEY`, `SECRET_KEY`)
4. For demo mode: set `USE_MOCK_DATA=true`
5. Deploy

### Docker

```bash
# Build and run with demo data
docker build -t ghostfolio-agent .
docker run -e USE_MOCK_DATA=true -p 8000:8000 ghostfolio-agent

# With real Ghostfolio data
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your-key \
  ghostfolio-agent
```

## Tech Stack

**Backend:** Python 3.11+, FastAPI, LangChain, LangGraph, OpenAI GPT-4o-mini

**Frontend:** React 19, TypeScript, Vite, Tailwind CSS

**Infrastructure:** Docker, Railway, LangSmith (tracing)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Ghostfolio](https://ghostfol.io/) - The wealth management platform this agent extends
- [LangChain](https://langchain.com/) - Agent framework
- [OpenAI](https://openai.com/) - Language models
