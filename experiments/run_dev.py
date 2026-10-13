"""Development batch: isolated B -> session -> runner -> read-only evidence -> C oracle -> A claim -> manifests.

python -m experiments.run_dev --plan experiments/plans/j1_mock.json
Every run is recorded whatever its outcome; nothing is rerun to pick results.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
import traceback

from actuarial.claims import calculate_claim
from contracts import models as wire
from evaluator.obligations import load_spec
from evaluator.verify import claim_event, evaluate_evidence
from runners import RUNNER_VERSION
from runners.attempts import AttemptLog
from runners.config import PaidRunsNotAuthorized, build, file_sha256, load_config
from runners.loop import run_episode
from runners.sandbox_client import AdminTransport, SessionTransport
from runners.tools import model_tool_specs, tool_specs_sha256

from .b_process import IsolatedB

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "artifacts/c_l0/runs"
COST_LEDGER = ROOT / "artifacts/c_l0/cost_ledger.jsonl"
CONTRACT = ROOT / "configs/insurance/research_contract_v0.1.json"
CODE_DIRS = ("runners", "evaluator", "experiments")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def code_hashes() -> dict[str, str]:
    files = sorted(p for d in CODE_DIRS for p in (ROOT / d).rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".json"))
    return {p.relative_to(ROOT).as_posix(): file_sha256(p) for p in files if "__pycache__" not in p.parts}


def git_head() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except OSError:
        return None


def prior_paid_cost() -> tuple[float, bool]:
    if not COST_LEDGER.exists():
        return 0.0, True
    total, known = 0.0, True
    for line in COST_LEDGER.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["cost_cny"] is None:
            known = False
        else:
            total += row["cost_cny"]
    return total, known


def run_one(spec: dict, b: IsolatedB, batch_dir: Path, index: int, experiment_id: str) -> dict:
    label = f"{index:02d}_{spec['label']}"
    run_dir = batch_dir / label
    run_dir.mkdir()
    config = load_config(ROOT / spec["config"])
    record = {"label": label, "fixture_id": spec["fixture_id"], "scenario": spec.get("scenario"),
              "config_id": config["config_id"], "run_status": "scheduled", "scheduled_at": now()}
    try:
        adapter, budget, pricing, global_cap = build(config, spec.get("scenario"))
    except PaidRunsNotAuthorized as error:
        record.update(run_status="not_started", stop_reason="paid_runs_not_authorized: " + str(error))
        write_json(run_dir / "manifest.json", record)
        return record
    remaining = None
    if adapter.paid:
        spent, known = prior_paid_cost()
        if not known:
            record.update(run_status="not_started", stop_reason="earlier paid cost unknown; refusing to exceed cap blindly")
            write_json(run_dir / "manifest.json", record)
            return record
        remaining = global_cap - spent
        if remaining <= 0:
            record.update(run_status="not_started", stop_reason="global C_MAX_COST_CNY exhausted")
            write_json(run_dir / "manifest.json", record)
            return record

    admin = AdminTransport(b.base_url, b.admin_token)
    created = admin.create_session({"tenant_id": "c-l0-development", "fixture_id": spec["fixture_id"],
                                    "experiment_id": experiment_id, "config_id": config["config_id"],
                                    "execution_source": adapter.execution_source})
    if created.http_status != 201:
        record.update(run_status="infra_error", stop_reason=f"create_session_http_{created.http_status}")
        write_json(run_dir / "manifest.json", record)
        return record
    session_info, token = created.payload["session"], created.payload["session_token"]
    write_json(run_dir / "case_context.json", created.payload["case_context"])
    session = SessionTransport(b.base_url, session_info["session_id"], token)
    del token, created
    session.faults = dict(getattr(adapter, "faults", {}))
    record.update(run_status="started", started_at=now(), session_id=session_info["session_id"],
                  episode_id=session_info["episode_id"], case_id=session_info["case_id"])

    specs = model_tool_specs()
    log = AttemptLog(run_dir / "attempts.jsonl")
    log.record("episode_start", session_id=session_info["session_id"], episode_id=session_info["episode_id"],
               config_id=config["config_id"], adapter=adapter.describe(), injected_faults=session.faults)
    try:
        result, transcript = run_episode(adapter, session, log, system_prompt=config["_prompt_text"],
                                         kickoff=config["kickoff"], tool_specs=specs, budget=budget, pricing=pricing,
                                         run_tag=secrets.token_hex(4), remaining_cost_cny=remaining)
        episode = result.to_dict()
    except Exception as error:  # Infrastructure failure is a recorded outcome, not a silent skip.
        log.record("runner_exception", error_type=type(error).__name__)
        episode, transcript = {"run_status": "infra_error", "stop_reason": "runner_exception:" + type(error).__name__,
                               "trace": traceback.format_exc()[-2000:]}, []
    write_json(run_dir / "transcript.json", transcript)
    if adapter.paid:
        COST_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with COST_LEDGER.open("a", encoding="utf-8") as ledger:
            ledger.write(json.dumps({"recorded_at": now(), "run": f"{batch_dir.name}/{label}", "config_id": config["config_id"],
                                     "prompt_tokens": episode.get("prompt_tokens"), "completion_tokens": episode.get("completion_tokens"),
                                     "cost_cny": episode.get("cost_cny"), "cost_basis": episode.get("cost_basis")}) + "\n")

    exported = admin.evidence(session_info["session_id"])
    evidence_sha = None
    if exported.http_status == 200:
        wire.EvidenceBundle.model_validate(exported.payload)
        evidence_sha = write_json(run_dir / "evidence.json", exported.payload)
        obligation_spec = load_spec(ROOT / spec["obligations"]) if spec.get("obligations") else None
        loss = evaluate_evidence(exported.payload, obligation_spec, evidence_sha)
        write_json(run_dir / "loss_result.json", loss)
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        claim = calculate_claim(claim_event(loss), contract)
        write_json(run_dir / "claim_A0.json", claim)
        record.update(loss_status=loss["loss_status"], total_committed_cents=loss["total_committed_cents"],
                      net_loss_cents=loss["net_loss_cents"], task_outcome=loss["task_outcome"],
                      claim_status=claim["claim_status"], payout_cents=claim["payout_cents"])
    else:
        record["evidence_export"] = f"http_{exported.http_status}"

    record.update({k: v for k, v in episode.items() if k != "trace"}, finished_at=now(),
                  execution_source=adapter.execution_source, adapter=adapter.describe(),
                  config_file=config["_path"], config_sha256=config["_sha256"], prompt_version=config["prompt_version"],
                  prompt_sha256=config["_prompt_sha256"], tool_specs_sha256=tool_specs_sha256(specs),
                  budget=config["budget"], pricing=config.get("pricing"), evidence_sha256=evidence_sha,
                  private_reasoning_turns=getattr(adapter, "private_reasoning_turns", 0),
                  injected_faults=dict(getattr(adapter, "faults", {})),
                  counts_as_formal_run=False)
    write_json(run_dir / "manifest.json", record)
    return record


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    args = parser.parse_args()
    plan_path = ROOT / args.plan
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    batch_id = f"{plan['batch_prefix']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    batch_dir = OUT_ROOT / batch_id
    batch_dir.mkdir(parents=True, exist_ok=False)
    db = ROOT / "var/c_runs" / batch_id / "b.sqlite3"
    batch = {"batch_id": batch_id, "plan_file": args.plan, "plan_sha256": file_sha256(plan_path), "plan": plan,
             "runner_version": RUNNER_VERSION, "contract_version": wire.VERSION, "git_head": git_head(),
             "python": sys.version, "code_sha256": code_hashes(), "started_at": now(),
             "b_instance": {"db": db.relative_to(ROOT).as_posix(), "host": "127.0.0.1 (random port)",
                            "admin_token": "in-memory only, not recorded"},
             "purpose": plan.get("purpose"), "counts_as_formal_run": False, "runs": []}
    with IsolatedB(db, batch_dir / "b_server.log") as b:
        for index, spec in enumerate(plan["runs"], 1):
            record = run_one(spec, b, batch_dir, index, plan["experiment_id"])
            batch["runs"].append(record)
            print(json.dumps({k: record.get(k) for k in ("label", "run_status", "stop_reason", "task_outcome",
                                                         "total_committed_cents", "loss_status", "net_loss_cents",
                                                         "claim_status", "cost_cny")}, ensure_ascii=False))
    batch["finished_at"] = now()
    write_json(batch_dir / "batch_manifest.json", batch)
    print("batch: " + batch_dir.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
