"""Confirm what a batch actually did with thinking, from the provider's own usage numbers.

A config can ask for a setting the provider ignores, so the request alone proves nothing.

  python -m experiments.check_reasoning risk-low-glm-20261106-120000 --expect on
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "var/risk_runs"


def reasoning_summary(batch_dir: Path) -> dict[str, Any]:
    runs = turns = thinking_turns = reasoning = completion = 0
    for path in sorted(batch_dir.glob("*/attempts.jsonl")):
        runs += 1
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line) if line else {}
            usage = record.get("usage") if record.get("kind") == "model_response" else None
            if usage:
                turns += 1
                completion += usage.get("completion_tokens") or 0
                tokens = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
                reasoning += tokens
                thinking_turns += 1 if tokens else 0
    return {"runs": runs, "turns": turns, "turns_with_reasoning": thinking_turns, "reasoning_tokens": reasoning,
            "completion_tokens": completion, "reasoning_share": round(reasoning / completion, 4) if completion else None,
            "reasoning_tokens_per_run": round(reasoning / runs, 1) if runs else None}


def matches(summary: dict[str, Any], expect: str) -> bool:
    if summary["turns"] == 0:
        return False
    return summary["reasoning_tokens"] > 0 if expect == "on" else summary["reasoning_tokens"] == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch")
    parser.add_argument("--expect", choices=("on", "off"), required=True)
    args = parser.parse_args(argv)
    summary = reasoning_summary(RAW_ROOT / args.batch)
    ok = matches(summary, args.expect)
    print(json.dumps({"batch": args.batch, "expect": args.expect, "ok": ok, **summary}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
