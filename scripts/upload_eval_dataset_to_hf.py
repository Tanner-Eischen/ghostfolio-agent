#!/usr/bin/env python3
"""
Upload the Ghostfolio Agent eval dataset to Hugging Face Hub.

Prerequisites:
  pip install datasets
  huggingface-cli login   # or set HF_TOKEN

Usage:
  python scripts/upload_eval_dataset_to_hf.py [--repo REPO] [--private]

Example:
  python scripts/upload_eval_dataset_to_hf.py --repo Tanner-Eischen/ghostfolio-agent-eval
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root for imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EVAL_CASES_PATH = ROOT / "evals" / "eval_cases" / "mvp_evals.json"
DATASET_README_PATH = ROOT / "evals" / "dataset_card_README.md"


def load_cases() -> list[dict]:
    """Load eval cases from JSON."""
    if not EVAL_CASES_PATH.exists():
        raise FileNotFoundError(f"Eval cases not found: {EVAL_CASES_PATH}")
    with open(EVAL_CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload Ghostfolio Agent eval dataset to Hugging Face")
    parser.add_argument(
        "--repo",
        default="Tanner-Eischen/ghostfolio-agent-eval",
        help="Hugging Face dataset repo (username/dataset-name)",
    )
    parser.add_argument("--private", action="store_true", help="Create private dataset")
    args = parser.parse_args()

    try:
        from datasets import Dataset
    except ImportError:
        print("Install datasets: pip install datasets")
        sys.exit(1)

    cases = load_cases()
    print(f"Loaded {len(cases)} eval cases from {EVAL_CASES_PATH}")

    # Build rows; keep lists/dicts for Dataset (supports nested structures)
    rows = []
    for c in cases:
        rows.append({
            "id": c["id"],
            "category": c["category"],
            "input": c["input"],
            "description": c.get("description", ""),
            "expected_tool_calls": c.get("expected_tool_calls", []),
            "expected_output_fields": c.get("expected_output_fields", []),
            "criteria": c.get("criteria", []),
        })

    dataset = Dataset.from_list(rows)
    print(f"Dataset: {dataset}")

    dataset.push_to_hub(args.repo, private=args.private)

    # Upload dataset card (README.md) if present
    readme_path = DATASET_README_PATH
    if readme_path.exists():
        try:
            from huggingface_hub import HfApi
            api = HfApi()
            api.upload_file(
                path_or_fileobj=str(readme_path),
                path_in_repo="README.md",
                repo_id=args.repo,
                repo_type="dataset",
            )
            print(f"Uploaded dataset card from {readme_path}")
        except Exception as e:
            print(f"Note: Could not upload README: {e}. Add README.md in the Hub UI.")

    print(f"Dataset uploaded to https://huggingface.co/datasets/{args.repo}")
    print("Load with: load_dataset({!r})".format(args.repo))


if __name__ == "__main__":
    main()
