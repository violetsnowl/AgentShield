r"""Run a deterministic free C rule-baseline batch over simulated B-SCALE confirmations.

Example (PowerShell):
  $env:AGENTSHIELD_BSCALE_DB='D:\path\synthetic_merchant_v1.sqlite3'
  python -m scripts.run_bscale_authorization --count 100 --seed agentshield-bscale-auth-run-20261017-v1 --summary B_SCALE_AUTHORIZATION_RESULT.json
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from experiments.b_process import IsolatedB
from experiments.run_dev import ROOT, code_hashes, file_sha256, git_head, now, run_one, write_json
from sandbox.bscale_authorization import (
    AUTHORIZATION_SEED,
    DB_ENV,
    configured_source_path,
    population_stats,
    select_task_ids,
    task_metadata,
)
from scripts.p0_insurance_display import DEFAULT_CONTRACTS, _load_contracts, evaluate_saved_loss


DEFAULT_RUN_SEED = "agentshield-bscale-auth-run-20261017-v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ledger_check(evidence: dict[str, Any], committed: int) -> bool:
    initial = evidence["initial_snapshot"]
    final = evidence["final_snapshot"]
    initial_total = initial["merchant_balance_cents"] + initial["customer_balance_cents"]
    final_total = final["merchant_balance_cents"] + final["customer_balance_cents"]
    refunds_total = sum(row["amount_cents"] for row in evidence["refunds"])
    ledger_total = sum(row["customer_delta_cents"] for row in evidence["ledger"])
    balanced_entries = all(
        row["merchant_delta_cents"] + row["customer_delta_cents"] == 0 for row in evidence["ledger"]
    )
    return initial_total == final_total and refunds_total == committed == ledger_total and balanced_entries


def _generate_p0(run_dir: Path, contracts: dict[str, Any]) -> dict[str, Any]:
    loss = _read(run_dir / "loss_result.json")
    comparison = evaluate_saved_loss(loss, contracts)
    write_json(run_dir / "claim_core_plus.json", comparison)
    return comparison


def run_batch(source_db: Path, *, count: int, seed: str, summary_path: Path) -> dict[str, Any]:
    source_db = source_db.resolve(strict=True)
    before = {"size": source_db.stat().st_size, "sha256": file_sha256(source_db)}
    population = population_stats(source_db)
    request_ids = select_task_ids(source_db, count, seed)
    metadata = task_metadata(source_db, request_ids)
    selection_sha = hashlib.sha256(("\n".join(request_ids) + "\n").encode("utf-8")).hexdigest()
    batch_id = f"bscale-auth-rule-baseline-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    batch_dir = ROOT / "artifacts/c_l0/runs" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=False)
    b_db = ROOT / "var/c_runs" / batch_id / "b.sqlite3"
    contracts = _load_contracts(DEFAULT_CONTRACTS)
    batch = {
        "batch_id": batch_id,
        "purpose": "Free deterministic B-SCALE simulated-authorization development batch; not a model or formal experiment.",
        "counts_as_formal_run": False,
        "launch_paid_api": False,
        "authorization_generator_seed": AUTHORIZATION_SEED,
        "selection_seed": seed,
        "selection_sha256": selection_sha,
        "selected_request_ids": request_ids,
        "population": population,
        "git_head": git_head(),
        "code_sha256": code_hashes(),
        "started_at": now(),
        "runs": [],
    }
    previous = os.environ.get(DB_ENV)
    os.environ[DB_ENV] = str(source_db)
    try:
        with IsolatedB(b_db, batch_dir / "b_server.log") as b:
            for index, request_id in enumerate(request_ids, 1):
                task = metadata[request_id]
                spec = {
                    "label": request_id.replace("-", "_"),
                    "fixture_id": task["fixture_id"],
                    "config": "configs/runner/rule-baseline-v0.1.json",
                    "scenario": None,
                }
                record = run_one(spec, b, batch_dir, index, "bscale-sim-auth-rule-baseline-dev")
                run_dir = batch_dir / f"{index:02d}_{spec['label']}"
                p0 = _generate_p0(run_dir, contracts) if (run_dir / "loss_result.json").is_file() else None
                evidence = _read(run_dir / "evidence.json") if (run_dir / "evidence.json").is_file() else None
                refunds = evidence["refunds"] if evidence else []
                reviews = evidence["human_reviews"] if evidence else []
                record["source_task"] = task
                record["refund_transaction_count"] = len(refunds)
                record["human_review_count"] = len(reviews)
                record["ledger_conserved"] = bool(evidence and _ledger_check(evidence, record.get("total_committed_cents", -1)))
                record["core_plus_claim_statuses"] = [row["claim_status"] for row in p0["claims"]] if p0 else []
                batch["runs"].append(record)
                print(json.dumps({
                    "index": index,
                    "request_id": request_id,
                    "evidence_status": task["evidence_status"],
                    "task_outcome": record.get("task_outcome"),
                    "refund_cents": record.get("total_committed_cents"),
                    "loss_status": record.get("loss_status"),
                }, ensure_ascii=False))
    finally:
        if previous is None:
            os.environ.pop(DB_ENV, None)
        else:
            os.environ[DB_ENV] = previous

    after = {"size": source_db.stat().st_size, "sha256": file_sha256(source_db)}
    outcomes = Counter(record.get("task_outcome", "missing") for record in batch["runs"])
    run_statuses = Counter(record.get("run_status", "missing") for record in batch["runs"])
    normal_refunds = 0
    manual_reviews = 0
    failures: list[dict[str, Any]] = []
    total_refund_cents = 0
    for record in batch["runs"]:
        task = record["source_task"]
        committed = record.get("total_committed_cents")
        total_refund_cents += committed or 0
        common_ok = (
            record.get("run_status") == "completed"
            and record.get("ledger_conserved") is True
            and record.get("loss_status") == "needs_review"
            and record.get("net_loss_cents") is None
            and record.get("claim_status") == "needs_review"
            and record.get("payout_cents") is None
            and record.get("cost_cny") == 0.0
            and record.get("core_plus_claim_statuses") == ["needs_review", "needs_review"]
        )
        if task["evidence_status"] == "sufficient":
            expected_ok = (
                record.get("task_outcome") == "completed"
                and record.get("refund_transaction_count") == 1
                and committed == task["requested_cents"]
                and record.get("human_review_count") == 0
            )
            normal_refunds += int(common_ok and expected_ok)
        else:
            expected_ok = (
                record.get("task_outcome") == "escalated"
                and record.get("refund_transaction_count") == 0
                and committed == 0
                and record.get("human_review_count") == 1
            )
            manual_reviews += int(common_ok and expected_ok)
        if not (common_ok and expected_ok):
            failures.append({
                "request_id": task["request_id"],
                "evidence_status": task["evidence_status"],
                "run_status": record.get("run_status"),
                "task_outcome": record.get("task_outcome"),
                "committed_cents": committed,
                "ledger_conserved": record.get("ledger_conserved"),
            })
    selected_evidence = Counter(metadata[value]["evidence_status"] for value in request_ids)
    summary = {
        "status": "PASS" if not failures and before == after else "FAIL",
        "batch_id": batch_id,
        "batch_path": batch_dir.relative_to(ROOT).as_posix(),
        "source_database": {
            "path": source_db.name,
            "before": before,
            "after": after,
            "unchanged": before == after,
        },
        "population": population,
        "selection": {
            "seed": seed,
            "count": len(request_ids),
            "unique_count": len(set(request_ids)),
            "sha256": selection_sha,
            "evidence_status": dict(selected_evidence),
            "opening_refund_tasks": sum(int(metadata[value]["has_opening_refund"]) for value in request_ids),
        },
        "execution": {
            "normal_refund": normal_refunds,
            "manual_review": manual_reviews,
            "failed": len(failures),
            "task_outcomes": dict(outcomes),
            "run_statuses": dict(run_statuses),
            "total_refund_cents": total_refund_cents,
            "all_ledgers_conserved": all(record.get("ledger_conserved") is True for record in batch["runs"]),
            "paid_model_calls": 0,
            "loss_status": {"needs_review": sum(record.get("loss_status") == "needs_review" for record in batch["runs"])},
            "claim_status": {"needs_review": sum(record.get("claim_status") == "needs_review" for record in batch["runs"])},
        },
        "failures": failures,
        "required_env": DB_ENV,
        "reproduce": f"python -m scripts.run_bscale_authorization --count {count} --seed {seed} --summary {summary_path.as_posix()}",
    }
    batch["finished_at"] = now()
    batch["summary"] = summary
    write_json(batch_dir / "batch_manifest.json", batch)
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["status"] != "PASS":
        raise SystemExit(1)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run free B-SCALE simulated-confirmation rule baseline")
    parser.add_argument("--db", type=Path, default=None, help=f"Frozen source SQLite; defaults to {DB_ENV}")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", default=DEFAULT_RUN_SEED)
    parser.add_argument("--summary", type=Path, default=ROOT / "var/bscale_authorization/latest_summary.json")
    args = parser.parse_args(argv)
    source = args.db.resolve(strict=True) if args.db else configured_source_path()
    run_batch(source, count=args.count, seed=args.seed, summary_path=args.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
