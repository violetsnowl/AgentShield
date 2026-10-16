"""Project the unpaid cost of the remaining development pretrial and the formal 56 runs.

Uses the three recorded L0 development calls. Does not contact a provider.
"""
import argparse
import json
from pathlib import Path
import sys

from .formal_gates import L1_AGENT_RUNS, PRETRIAL_TARGET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "experiments/fixtures/observed_dev_cost_ledger.jsonl"
ESTIMATE_PATH = ROOT / "experiments/fixtures/cost_pretrial_estimate.json"


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if not rows:
        raise ValueError("cost ledger is empty")
    if any(row.get("cost_cny") is None for row in rows):
        raise ValueError("unknown cost cannot be projected as zero")
    return rows


def project(rows: list[dict], *, safety_factor: int = 3) -> dict:
    costs = [row["cost_cny"] for row in rows]
    unit = max(costs)
    remaining = max(0, PRETRIAL_TARGET - len(rows))
    observed = round(sum(costs), 6)
    unit_rounded = round(unit, 6)
    pretrial_remaining = round(remaining * unit * safety_factor, 6)
    formal = round(L1_AGENT_RUNS * unit * safety_factor, 6)
    return {
        "observed_dev_runs": len(rows),
        "observed_cost_cny_upper": observed,
        "unit_upper_cny": unit_rounded,
        "pretrial_target": PRETRIAL_TARGET,
        "pretrial_remaining_runs": remaining,
        "pretrial_counts_toward_formal_56": False,
        "safety_factor": safety_factor,
        "safety_note": "3x covers longer formal tasks than the two short development templates; it is a budget request, not a quote",
        "pretrial_remaining_authorization_cny": pretrial_remaining,
        "formal_56_authorization_cny": formal,
        "requested_authorization_cny": round(pretrial_remaining + formal, 6),
        "observed_rate_without_safety_cny": {
            "pretrial_remaining": round(remaining * unit, 6),
            "formal_56": round(L1_AGENT_RUNS * unit, 6),
        },
        "pricing_basis": rows[0].get("cost_basis"),
        "paid_api_called": False,
        "budget_confirmed": False,
        "formal_runs_started": False,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    estimate = project(load_rows(Path(args.ledger)))
    text = json.dumps(estimate, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        ESTIMATE_PATH.write_text(text, encoding="utf-8")
        print("wrote " + ESTIMATE_PATH.relative_to(ROOT).as_posix())
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
