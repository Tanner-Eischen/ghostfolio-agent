# Ghostfolio Agent

> AI-powered portfolio assistant for [Ghostfolio](https://ghostfol.io) - Analyze, categorize, and assess risk with natural language

[![PyPI version](https://badge.fury.io/py/ghostfolio-agent.svg)](https://badge.fury.io/py/ghostfolio-agent)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Portfolio Analysis** - Get insights on holdings, allocation, and performance
- **Transaction Categorization** - Classify transactions and identify patterns
- **Risk Assessment** - Evaluate diversification and concentration risk
- **Market Data Lookup** - Fetch current prices for stocks, ETFs, and crypto
- **Compliance Checking** - Validate against wash sale, day trading, and concentration rules

## Quick Start

### Installation

```bash
pip install ghostfolio-agent
```

### Setup

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Add your API keys to `.env`:
```bash
ANTHROPIC_API_KEY=your_key_here
LANGCHAIN_API_KEY=your_key_here
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

# Check compliance
response = await agent.chat("Did I violate any wash sale rules?")
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
│   │   ├── transaction_categorize.py
│   │   ├── risk_assessment.py
│   │   ├── market_data_lookup.py
│   │   └── compliance_check.py
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
| `transaction_categorize` | Classify transactions, identify patterns |
| `risk_assessment` | Evaluate diversification, concentration, volatility |
| `market_data_lookup` | Fetch current prices from Yahoo Finance/CoinGecko |
| `compliance_check` | Validate against financial rules |

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/ghostfolio-agent/ghostfolio-agent.git
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
python evals/run_evals.py
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | Required |
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
   LANGCHAIN_API_KEY=lsv2_pt_xxxxxxxx
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_PROJECT=ghostfolio-agent
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
- **LLM**: Claude 3.5 Sonnet
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

- 📖 [Documentation](https://github.com/ghostfolio-agent/ghostfolio-agent#readme)
- 🐛 [Issue Tracker](https://github.com/ghostfolio-agent/ghostfolio-agent/issues)
- 💬 [Discussions](https://github.com/ghostfolio-agent/ghostfolio-agent/discussions)
