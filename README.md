# Ghostfolio Agent

> AI-powered portfolio assistant for [Ghostfolio](https://ghostfol.io) - Analyze, categorize, and assess risk with natural language

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Deployed on Railway](https://img.shields.io/badge/deployed-railway-purple)](https://ghostfolio-agent-production-e24d.up.railway.app)

**Live Demo:** https://ghostfolio-agent-production-e24d.up.railway.app

## Features

- **Portfolio Analysis** - Get insights on holdings, allocation, and performance
- **Risk Assessment** - Evaluate diversification and concentration risk
- **Market Data Lookup** - Fetch current prices for stocks, ETFs, and crypto
- **Verification Layer** - Confidence scoring, escalation signals, and domain checks
- **MVP Eval Framework** - Atomic, objective pass/fail evals with Streamlit visualization

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Tanner-Eischen/ghostfolio-agent.git
cd ghostfolio-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

### Setup

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Add your API keys to `.env`:
```bash
OPENAI_API_KEY=your_key_here
LANGSMITH_API_KEY=your_key_here
GHOSTFOLIO_ACCESS_TOKEN=your_token_here
```

### Run the Agent

```bash
# Start the API server
ghostfolio-agent

# Or run with uvicorn directly
uvicorn src.api.routes:app --reload
```

### Run the Streamlit Frontend

```bash
streamlit run app/streamlit_app.py
```

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
├── tests/              # Test suite
└── app/                # Streamlit frontend
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

## Tech Stack

- **Agent Framework**: LangChain + LangGraph
- **LLM**: OpenAI GPT-4o-mini (configurable)
- **Observability**: LangSmith
- **Backend**: FastAPI
- **Frontend**: Streamlit
- **Testing**: pytest, pytest-asyncio

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

This project is deployed on Railway. To deploy your own instance:

1. Fork this repository
2. Create a new project on [Railway](https://railway.app)
3. Connect your GitHub repository
4. Set the required environment variables (see `.env.example`)
5. Deploy!

Required environment variables:
- `OPENAI_API_KEY` - Your OpenAI API key
- `SECRET_KEY` - Random string for session encryption
- `LANGSMITH_API_KEY` - For observability (optional)
