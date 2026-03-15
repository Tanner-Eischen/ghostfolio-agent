# Eval Cases Directory

MVP eval cases for the Ghostfolio Agent. All cases use the atomic criteria schema.

## Structure

```
eval_cases/
└── mvp_evals.json    # MVP suite (10+ cases)
```

## Case Categories

Categories are labels for eval intent; all use the same atomic check semantics:

- **tool_selection**: Correct tool chosen for the query.
- **multi_step**: Query requires chaining multiple tools.
- **correctness**: Output accuracy and required fields present.
- **tool_execution**: Tool runs successfully and returns expected structure.
- **edge_case**: Ambiguous or partially specified queries; agent should still route correctly.
- **adversarial**: Prompt-injection or manipulative input; agent must remain grounded to domain tools.

## MVP Schema

Each eval case must use this format:

```json
{
  "id": "MVP-001",
  "category": "mvp",
  "input": "What's my portfolio worth?",
  "description": "Portfolio value query should use portfolio_analysis tool",
  "expected_tool_calls": ["portfolio_analysis"],
  "expected_output_fields": ["total_value", "holdings"],
  "criteria": [
    {
      "id": "C1",
      "description": "portfolio_analysis tool was called",
      "check_type": "tool_called",
      "expected": "portfolio_analysis"
    },
    {
      "id": "C2",
      "description": "Response includes total_value field",
      "check_type": "field_present",
      "expected": "total_value"
    }
  ]
}
```

### Check Types

- **tool_called**: `expected` = tool name. Pass if that tool appears in the list of tools invoked.
- **field_present**: `expected` = field name. Pass **only** if the field exists as a **top-level key** in at least one structured object in `tool_outputs` for that run. Natural-language response text does not count.

### Pass Rule

Overall case pass = all criteria pass (AND across criteria).

## Usage

```bash
python evals/run_evals.py --category mvp --validate   # Validate format
python evals/run_evals.py --category mvp              # Run MVP evals
```

## Consuming the dataset elsewhere

- **PyPI package (no Hugging Face):** `pip install ghostfolio-agent-eval` then `from ghostfolio_agent_eval import load_eval_cases, get_dataset_path`. The package lives under `packages/ghostfolio_agent_eval` and can be published with `python -m build` and `twine upload dist/*`.
- **Hugging Face:** Run `python scripts/upload_eval_dataset_to_hf.py` to push the same cases to the Hub (see script docstring).
