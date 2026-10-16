"""Check the formal L1 plan and refuse to start it.

python -m experiments.run_formal --plan experiments/plans/l1_formal_blocked.json
The committed plan is blocked. This checkpoint does not launch the 56 agent runs
or the 28 baseline runs, and it does not read held-out answers.
"""
import argparse
import json
import os
from pathlib import Path
import sys

from .formal_gates import formal_blockers

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    plan = json.loads((ROOT / args.plan).read_text(encoding="utf-8"))
    blockers = formal_blockers(plan, execute=args.execute, env_flag=os.environ.get("C_FORMAL_RUN_AUTHORIZED"))
    report = {"plan": args.plan, "launch": False, "paid_api_called": False, "blockers": blockers}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
