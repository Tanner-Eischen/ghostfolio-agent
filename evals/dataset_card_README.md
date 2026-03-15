# Ghostfolio Agent Eval Dataset

Evaluation dataset for **Ghostfolio Agent**: an AI assistant over [Ghostfolio](https://ghostfol.io/) for natural-language portfolio and market queries. This dataset is used to regression-test the agent on tool selection, correctness, tool execution, edge cases, adversarial inputs, and multi-step queries.

## Dataset Summary

- **75 test cases** across 6 categories
- **Domain:** Finance / portfolio management (Ghostfolio-backed)
- **Purpose:** Evaluate agent tool-calling, output structure, and safety

## Categories

| Category        | Count | Description |
|----------------|-------|-------------|
| tool_selection | 14    | Query should invoke the correct tool(s) |
| correctness    | 15    | Tool output contains expected fields (e.g. total_value, holdings) |
| tool_execution | 10    | Tool runs and returns valid structure |
| edge_case      | 11    | Unusual phrasing, missing data, invalid input |
| adversarial    | 11    | Prompt injection / harmful intent; agent must stay grounded |
| multi_step     | 11+   | Multiple tools required (e.g. portfolio + risk) |

## Data Fields

| Column                  | Type   | Description |
|-------------------------|--------|-------------|
| id                      | string | Case ID (e.g. MVP-001) |
| category                | string | One of the categories above |
| input                   | string | User query / prompt |
| description             | string | Short description of what is being tested |
| expected_tool_calls     | list   | Tool names that should be invoked |
| expected_output_fields | list   | Field names that should appear in tool output |
| criteria                | list   | List of checks: `check_type` (e.g. tool_called, field_present), `expected` value |

## Usage

```python
from datasets import load_dataset

ds = load_dataset("Tanner-Eischen/ghostfolio-agent-eval")
# or after upload with your repo name
# ds = load_dataset("username/ghostfolio-agent-eval")
```

Each row is one eval case. Use `input` as the agent prompt and validate the agent response against `expected_tool_calls`, `expected_output_fields`, and `criteria`.

## Related

- **Source repo:** [ghostfolio-agent](https://github.com/Tanner-Eischen/ghostfolio-agent)
- **Eval runner:** `evals/run_evals.py` in the repo
- **License:** Same as the Ghostfolio Agent project (see repo)

## Citation

If you use this dataset, please link to the [Ghostfolio Agent](https://github.com/Tanner-Eischen/ghostfolio-agent) repository and, if applicable, [Ghostfolio](https://ghostfol.io/).
