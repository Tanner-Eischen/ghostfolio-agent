# Ghostfolio Agent - Architecture Document

**Gauntlet AI AgentForge Week 2**

---

## 1. Domain & Use Cases

### Why This Domain

Financial portfolio management is a high-stakes domain where AI errors have real monetary consequences. Users need accurate, verified information about their investments without hallucinated numbers or misleading advice. Ghostfolio is an open-source wealth management platform with 4K+ GitHub stars, making it an ideal target for a meaningful open-source contribution.

### Problems Solved

1. **Natural Language Access** - Users can query their portfolio without navigating complex UIs
2. **Risk Awareness** - Automated assessment of diversification and concentration risk
3. **Compliance Monitoring** - Detection of wash sales, pattern day trading, concentration violations
4. **Market Data Integration** - Unified access to stock prices (Yahoo Finance) and crypto (CoinGecko)

### Target Users

- Individual investors using Ghostfolio for portfolio tracking
- Financial advisors needing quick portfolio summaries
- Compliance officers monitoring trading patterns

---

## 2. Agent Architecture

### Framework Choice: LangChain + LangGraph

**Why LangChain:** Extensive tool integration ecosystem, structured output support, well-documented
**Why LangGraph:** State machine for multi-step reasoning, built-in memory management

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                         │
│              (Streamlit / REST API / CLI)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    GhostfolioAgent                          │
│                  (LangChain + LangGraph)                    │
│                                                             │
│  • System prompt with tool-calling rules                    │
│  • Conversation history with 24h TTL                        │
│  • Mixed-intent handling (adversarial + legitimate)         │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   Tool Layer     │ │ Verification     │ │  Observability   │
│    (5 Tools)     │ │    Layer         │ │                  │
│                  │ │                  │ │ • LangSmith      │
│ • portfolio_     │ │ • Confidence     │ │   Tracing        │
│   analysis       │ │   Scorer (0-100) │ │ • Token Usage    │
│ • risk_          │ │ • Fact Checker   │ │ • Latency        │
│   assessment     │ │ • Constraints    │ │   Tracking       │
│ • market_data    │ │ • Pipeline       │ │ • Trace URLs     │
│ • compliance     │ │                  │ │                  │
│ • transaction    │ │ Escalation at    │ │                  │
│                  │ │ <70% confidence  │ │                  │
└──────────────────┘ └──────────────────┘ └──────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Clients                              │
│   Ghostfolio API │ Yahoo Finance │ CoinGecko               │
└─────────────────────────────────────────────────────────────┘
```

### Reasoning Approach

The agent uses a simple but effective pattern:
1. **Tool Selection** - LLM selects appropriate tools based on query intent
2. **Parallel Execution** - Multiple tools can be invoked simultaneously
3. **Response Synthesis** - LLM combines tool outputs into natural language
4. **Verification** - All responses pass through verification pipeline before return

### Tool Design

| Tool | Input | Output | Verification |
|------|-------|--------|--------------|
| `portfolio_analysis` | timeframe, account_id | total_value, holdings, diversification_score | Value >= 0, score 0-100 |
| `risk_assessment` | - | overall_risk_score, concentration_risk, recommendations | Score 0-100, valid risk level |
| `market_data_lookup` | symbols[], metrics[] | prices, change_24h, market_cap | Fresh data (<24h), valid prices |
| `compliance_check` | - | violations[], severity | Valid severity levels |
| `transaction_categorize` | date_range | patterns[], insights | Valid pattern types |

---

## 3. Verification Strategy

### What Checks We Implemented

1. **Confidence Scoring** (`confidence.py`)
   - Data completeness assessment
   - Tool success rate tracking
   - Response grounding verification
   - Levels: VERY_HIGH (90+), HIGH (80-89), MEDIUM (70-79), LOW (50-69)

2. **Fact Checking** (`fact_checker.py`)
   - Numerical claims within tolerance (5%)
   - Citation extraction and verification
   - Market data freshness (<24 hours)
   - Portfolio total cross-reference

3. **Constraint Validation** (`constraints.py`)
   - No negative financial values
   - Concentration limits (<25% single position)
   - Daily change threshold (<20%)
   - NaN/Inf detection

4. **Escalation System**
   - Automatic escalation at <70% confidence
   - Triggers: critical violations, large transactions, unusual changes

### Why These Checks

Financial domains require fail-closed behavior. A wrong portfolio value or missed risk warning has real consequences. The verification layer ensures:
- **Accuracy** - Numbers match tool outputs
- **Completeness** - All required fields present
- **Freshness** - Market data is current
- **Safety** - No investment advice given

---

## 4. Evaluation Results

### Test Suite Composition

**69 test cases across 4 categories:**

| Category | Count | Purpose |
|----------|-------|---------|
| Happy Path | 25 | Standard queries with expected outcomes |
| Edge Cases | 17 | Boundary conditions, invalid inputs |
| Adversarial | 14 | Prompt injection, harmful requests |
| Correctness | 13 | Output validation, field checks |

### Results

```
┌─────────────────────────────────────────────────┐
│  EVALUATION RESULTS: 69/69 PASSED (100%)       │
├─────────────────────────────────────────────────┤
│  ✓ Happy Path:    25/25 (100%)                 │
│  ✓ Edge Cases:    17/17 (100%)                 │
│  ✓ Adversarial:   14/14 (100%)                 │
│  ✓ Correctness:   13/13 (100%)                 │
└─────────────────────────────────────────────────┘
```

### Key Test Scenarios

- **MVP-001**: Portfolio value query → `portfolio_analysis` called
- **MVP-021**: Invalid symbol lookup → `market_data_lookup` called (returns error gracefully)
- **MVP-059**: Code injection + portfolio query → Injection blocked, portfolio analyzed
- **MVP-066**: Risk assessment → `overall_risk_score` in valid range 0-100

### Failure Modes Addressed

1. **Hallucination** - Fact checker catches unverified claims
2. **Wrong Tool Selection** - Eval cases verify correct tool calls
3. **Injection Attacks** - Mixed-intent handler strips malicious input
4. **Stale Data** - Freshness checks warn on old market data

---

## 5. Observability Setup

### LangSmith Integration

All agent operations are traced with LangSmith:

```python
# Automatic tracing on all agent methods
@traceable(name="agent_chat_with_context", run_type="chain")
async def chat_with_context(self, message: str, ...):
    ...
```

### What We Track

| Metric | Description |
|--------|-------------|
| Request Tracing | Full cycle: input → reasoning → tools → output |
| Token Usage | Input/output tokens per request, model used |
| Latency | LLM time, tool time, verification time |
| Confidence | Per-response confidence score |
| Tool Calls | Which tools called, parameters, outputs |
| Verification | Pass/fail status, violations, escalation |

### Dashboard Access

- **URL:** https://smith.langchain.com
- **Project:** AgentForge
- Each API response includes `trace_url` for direct trace access

---

## 6. Open Source Contribution

### What We Released

**Evaluation Dataset** - 69 test cases for financial agent evaluation

The `evals/eval_cases/mvp_evals.json` file contains structured test cases that others can use to:
- Evaluate their own financial agents
- Learn evaluation patterns for domain-specific agents
- Understand adversarial testing approaches

### Test Case Format

```json
{
  "id": "MVP-001",
  "category": "happy_path",
  "input": "What is my portfolio value?",
  "description": "Basic portfolio value query",
  "expected_tool_calls": ["portfolio_analysis"],
  "expected_output_fields": ["total_value"],
  "criteria": [
    {"id": "C1", "check_type": "tool_called", "expected": "portfolio_analysis"},
    {"id": "C2", "check_type": "field_present", "expected": "total_value"}
  ]
}
```

### Location

- **Repository:** https://github.com/Tanner-Eischen/ghostfolio-agent
- **Dataset:** `evals/eval_cases/mvp_evals.json`
- **License:** MIT

---

## Summary

| Component | Status |
|-----------|--------|
| Agent | ✅ LangChain + LangGraph |
| Tools | ✅ 5 specialized tools |
| Verification | ✅ 4-layer pipeline |
| Observability | ✅ LangSmith tracing |
| Evaluation | ✅ 69/69 tests passing |
| Deployment | ✅ Railway (live) |
| Documentation | ✅ README + Architecture |
| Open Source | ✅ Eval dataset released |

**Live Demo:** https://ghostfolio-agent-production-e24d.up.railway.app
