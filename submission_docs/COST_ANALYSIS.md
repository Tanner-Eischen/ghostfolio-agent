# Cost Analysis: Ghostfolio Agent

This document is for **service providers** who run the Ghostfolio Agent and front the compute (LLM, infrastructure). Use it together with the in-app **Observability & Cost** page to project and monitor costs as you scale users.

It provides cost projections for running the Ghostfolio Agent in production, based on actual development usage data and scaling assumptions.

## Executive Summary

| Metric | Value |
|--------|-------|
| Default Model | GPT-4o-mini |
| Avg Cost per Query | ~$0.001 - $0.002 |
| Estimated Monthly Cost (1K users, 10 queries/day) | ~$180 - $300 |
| Verification Overhead | ~20% additional tokens |

### Production cost projections (PDF submission format)

| Users | Monthly cost ($/month) |
|-------|-------------------------|
| 100 | ~$18 |
| 1,000 | ~$180 |
| 10,000 | ~$1,800 |
| 100,000 | ~$18,000 |

*Assumptions: 10 queries per user per day; ~600 tokens per query (400 in / 200 out); GPT-4o-mini pricing. See tables below for detail.*

---

## Development Costs (Actual Data)

Based on usage logged during development and testing phases, retrieved from `usage_log.json`:

### Token Usage Statistics

| Metric | Value |
|--------|-------|
| Total Requests | Tracked in `data/usage_log.json` |
| Avg Input Tokens | ~400 per query |
| Avg Output Tokens | ~200 per query |
| Total Avg Tokens | ~600 per query |

### Per-Query Cost Breakdown

| Component | Input Cost | Output Cost | Total |
|-----------|------------|-------------|-------|
| System Prompt | ~300 tokens | - | ~$0.00005 |
| User Query + Context | ~100 tokens | - | ~$0.00002 |
| LLM Response | - | ~150 tokens | ~$0.00009 |
| Tool Call (avg 1-2) | ~50 tokens | ~50 tokens | ~$0.00004 |
| Verification | ~100 tokens | ~50 tokens | ~$0.00002 |
| **Total per Query** | | | **~$0.0002 - $0.002** |

---

## Production Projections

### Scaling Model

Projections assume:
- **Avg tokens per query**: 600 (400 input + 200 output)
- **Default model**: GPT-4o-mini ($0.15/1M input, $0.60/1M output)
- **Queries per user per day**: 10 (conservative estimate)
- **Tool call rate**: 90% of queries use 1+ tools
- **Verification overhead**: 20% additional tokens

### Cost by User Scale

| Users | Queries/Day | Daily Cost | Monthly Cost | Annual Cost |
|-------|-------------|------------|--------------|-------------|
| 10 | 100 | $0.06 | $1.80 | $21.90 |
| 100 | 1,000 | $0.60 | $18.00 | $219.00 |
| 1,000 | 10,000 | $6.00 | $180.00 | $2,190.00 |
| 10,000 | 100,000 | $60.00 | $1,800.00 | $21,900.00 |
| 100,000 | 1,000,000 | $600.00 | $18,000.00 | $219,000.00 |

### Cost by Model Selection

For higher-quality responses, you may choose different models:

| Model | Input ($/1M) | Output ($/1M) | Cost/Query | Monthly (1K users) |
|-------|--------------|---------------|------------|-------------------|
| GPT-4o-mini | $0.15 | $0.60 | ~$0.0002 | ~$60 |
| GPT-4o | $2.50 | $10.00 | ~$0.003 | ~$900 |
| Claude 3.5 Sonnet | $3.00 | $15.00 | ~$0.004 | ~$1,200 |
| Claude 3.5 Haiku | $0.25 | $1.25 | ~$0.0004 | ~$120 |

---

## Cost Optimization Strategies

### 1. Model Selection Guidelines

| Use Case | Recommended Model | Rationale |
|----------|------------------|-----------|
| Simple portfolio queries | GPT-4o-mini | Fast, cheap, accurate |
| Complex analysis | GPT-4o | Better reasoning |
| High-volume production | GPT-4o-mini + caching | Cost efficiency |
| Premium tier users | GPT-4o | Better quality |

### 2. Caching Opportunities

- **System prompt caching**: Cache the ~300 token system prompt
- **Tool schema caching**: Cache tool definitions
- **Portfolio data caching**: Cache portfolio snapshot for 5-15 minutes
- **Market data caching**: Cache prices for 1-5 minutes

**Estimated savings**: 30-50% reduction in input tokens

### 3. Batching Strategies

- Combine multiple portfolio queries into single requests
- Batch market data lookups for multiple symbols
- Aggregate analytics requests

### 4. Query Optimization

- Shorter system prompts for simple queries
- Skip verification for high-confidence responses
- Stream responses to reduce perceived latency (no cost impact)

---

## Monitoring & Budgeting

### Recommended Budget Alerts

| Threshold | Action |
|-----------|--------|
| $10/day | Review usage patterns |
| $50/day | Investigate potential abuse |
| $100/day | Emergency review required |

### Usage Tracking

The agent includes built-in usage tracking via `src/utils/usage_tracker.py`:

```python
from src.utils.usage_tracker import get_usage_stats, get_cost_projections

# Get current usage stats
stats = get_usage_stats()
print(f"Total cost: ${stats['total_cost']}")
print(f"Avg cost per request: ${stats['avg_cost_per_request']}")

# Get projections for 1000 queries/day
projections = get_cost_projections(queries_per_day=1000)
print(f"Monthly projection: ${projections['monthly_cost']}")
```

### API Endpoints for Monitoring

- `GET /finances/usage` - Current usage statistics
- `GET /finances/projections?queries_per_day=N` - Cost projections

---

## Assumptions & Caveats

### Assumptions Made

1. **Query complexity**: Average query uses 1-2 tools
2. **Response length**: ~150 tokens average
3. **User behavior**: 10 queries per user per day
4. **Geographic distribution**: Single-region deployment
5. **No caching**: Projections assume no response caching

### Factors That May Increase Costs

- High-volume users (>50 queries/day)
- Complex multi-step queries
- Large portfolio datasets
- Frequent market data lookups
- Premium model selection

### Factors That May Decrease Costs

- Effective caching implementation
- Prompt optimization
- User query batching
- Volume discounts (enterprise agreements)

---

## Recommendations

### For MVP/Development
- Use GPT-4o-mini exclusively
- Enable usage logging
- Monitor costs weekly

### For Production Launch
- Implement portfolio data caching (5 min TTL)
- Add market data caching (1 min TTL)
- Set budget alerts at $50/day

### For Scale (10K+ users)
- Negotiate enterprise pricing
- Consider dedicated capacity
- Implement query queuing for rate limiting

---

*Last updated: 2026-02-26*
*Data source: `src/utils/usage_tracker.py`, `data/usage_log.json`*
