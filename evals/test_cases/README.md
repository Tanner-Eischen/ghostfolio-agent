# Test Cases Directory

This directory contains evaluation test cases for the Ghostfolio Agent.

## Structure

```
test_cases/
├── happy_path.json      # 20+ standard portfolio queries
├── edge_cases.json      # 10+ edge cases (empty data, invalid inputs)
├── adversarial.json     # 10+ prompt injection and harmful requests
└── multi_step.json      # 10+ complex analysis requiring tool chains
```

## Test Case Format

Each test case follows this schema:

```json
{
  "id": "HP-001",
  "category": "happy_path",
  "input": "What's my portfolio worth?",
  "expected_tools": ["portfolio_analysis"],
  "expected_output_contains": ["total value", "holdings"],
  "pass_criteria": {
    "tool_selection_correct": true,
    "response_time_ms_max": 5000,
    "contains_expected_phrases": true,
    "no_errors": true
  }
}
```

## Adding New Test Cases

1. Choose the appropriate category file
2. Add your test case with a unique ID
3. Run `python evals/run_evals.py --validate` to verify format
4. Run `python evals/run_evals.py` to execute tests
