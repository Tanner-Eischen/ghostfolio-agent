# Ghostfolio Agent Skills

This repo includes five skills: one meta-skill for writing skills and four domain skills (financial output evaluation, verification/escalation, agent trace triage, AI unit economics). Each skill lives in `skills/<skill-name>/SKILL.md` and can be loaded by agents (e.g. Cursor/Codex) when the task matches the skill description.

## Skills

| Skill | Path | When to use |
|-------|------|-------------|
| **write-skills** | [skills/write-skills/SKILL.md](skills/write-skills/SKILL.md) | Creating a new skill, editing SKILL.md, or reviewing skill descriptions and parameters so skills trigger reliably and minimize cognitive load. |
| **evaluate-financial-tool-outputs** | [skills/evaluate-financial-tool-outputs/SKILL.md](skills/evaluate-financial-tool-outputs/SKILL.md) | Run four quality gates on one financial tool output; return pass/fail and recommended action. Use when validating one quote, bar, holding, PnL, or valuation before display or automated decision. |
| **verify-and-escalate-ambiguous-market-data** | [skills/verify-and-escalate-ambiguous-market-data/SKILL.md](skills/verify-and-escalate-ambiguous-market-data/SKILL.md) | Classify one ambiguous market-data incident and return escalation decision and HITL packet. Use when feeds disagree, timestamps lag, or data quality is insufficient for safe automation. |
| **triage-agent-traces-for-tool-release** | [skills/triage-agent-traces-for-tool-release/SKILL.md](skills/triage-agent-traces-for-tool-release/SKILL.md) | Decide release readiness for one tool-calling workflow from trace evidence and gates. Use before deploying new tool calls, schema updates, or model swaps; for canary/rollback decisions. |
| **estimate-ai-unit-economics** | [skills/estimate-ai-unit-economics/SKILL.md](skills/estimate-ai-unit-economics/SKILL.md) | Produce cost estimate for one agent workflow (tokens, tools, retries, HITL, infra); return per-request and per-success economics plus scenarios. Use for pricing, budgeting, or optimization. |

## Structure

```
skills/
├── write-skills/
│   └── SKILL.md
├── evaluate-financial-tool-outputs/
│   └── SKILL.md
├── verify-and-escalate-ambiguous-market-data/
│   └── SKILL.md
├── triage-agent-traces-for-tool-release/
│   └── SKILL.md
└── estimate-ai-unit-economics/
    └── SKILL.md
```

Each `SKILL.md` has YAML frontmatter (`name`, `description`) for triggering—kept to ~50–150 words—and a body with input/output schemas, error handling, idempotency notes, and implementation. Use the skill when the user request or task matches the description in the frontmatter.
