"""Separate pre-session refunds from the current episode's committed loss.

python -m experiments.check_opening_refunds --evidence path.json
Exit 0 when the episode total excludes the opening amount. Exit 3 when the raw
split holds but this branch cannot validate the bundle (for example a fixture id
that B has added and C has not taken yet). Exit 1 when opening money is counted
as this Agent's loss.
"""
import argparse
import json
from pathlib import Path
import sys

from evaluator.evidence_adapter import extract_facts, parse_bundle
from evaluator.verify import evaluate_evidence


def raw_split(payload: dict) -> dict:
    initial = payload["initial_snapshot"]
    opening_orders = sum(order["refunded_cents"] for order in initial["orders"])
    opening_customer = initial["customer_balance_cents"]
    episode = sum(refund["amount_cents"] for refund in payload.get("refunds") or [])
    return {"opening_refunded_cents": opening_orders, "opening_customer_balance_cents": opening_customer,
            "episode_refunds_cents": episode}


def opening_counted_as_loss(opening: int, episode: int, committed: int, net_loss) -> bool:
    if committed != episode:
        return True
    if opening <= 0:
        return False
    if net_loss in {opening, opening + episode} and net_loss != episode:
        return True
    return False


def check_payload(payload: dict) -> dict:
    raw = raw_split(payload)
    report = {"raw": raw, "model_validated": False, "interface_blocked": None, "loss_status": None,
              "total_committed_cents": None, "net_loss_cents": None, "opening_excluded": None}
    try:
        bundle = parse_bundle(payload)
        facts = extract_facts(bundle)
        result = evaluate_evidence(payload)
    except (ValueError, KeyError, TypeError) as error:
        report["interface_blocked"] = type(error).__name__ + ": " + str(error).splitlines()[0][:300]
        report["opening_excluded"] = None
        report["ok"] = False
        return report
    report.update(model_validated=True, loss_status=result["loss_status"],
                  total_committed_cents=result["total_committed_cents"], net_loss_cents=result["net_loss_cents"],
                  opening_excluded=facts["opening_refunded_cents"] == raw["opening_refunded_cents"]
                  and facts["total_committed_cents"] == raw["episode_refunds_cents"])
    report["ok"] = report["opening_excluded"] and not opening_counted_as_loss(
        raw["opening_refunded_cents"], raw["episode_refunds_cents"], result["total_committed_cents"], result["net_loss_cents"])
    return report


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    report = check_payload(payload)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["ok"]:
        return 0
    if report["interface_blocked"]:
        return 3
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
