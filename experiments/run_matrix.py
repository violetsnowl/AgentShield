"""Risk experiment: the same tasks under each control profile, in parallel, resumable.

Free boundary probe:
  python -m experiments.run_matrix --config configs/runner/red-team-v0.1.json --per-family 10 --prefix risk-probe
Real model, inside the approved budget:
  python -m experiments.run_matrix --config configs/runner/deepseek-risk-v0.1.json --per-family 3 --prefix risk-pilot \
      --workers 4 --paid --allowance-cny 5
Harder task set: add --task-set v2.

Every attempt is kept. A rerun with --resume repeats only cells that never finished,
and picks nothing by result. Raw evidence goes to var/ (Git-ignored); compact rows
and the summary go to artifacts/risk_runs/.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import secrets
import sys
import threading
import traceback

from actuarial.claims import calculate_claim
from contracts import models as wire
from evaluator.verify import claim_event, evaluate_evidence
from runners import RUNNER_VERSION
from runners.attempts import AttemptLog
from runners.config import build, load_config
from runners.loop import run_episode
from runners.sandbox_client import AdminTransport, SessionTransport
from runners.tools import model_tool_specs, tool_specs_sha256
from sandbox.bscale_authorization import DB_ENV
from sandbox.risk_tasks import DEFAULT_SEED, FAMILIES, RISK_FIXTURE_RE, select_risk_tasks
from sandbox.risk_tasks_hard import HARD_FAMILIES, HARD_SEED, select_hard_tasks
from scripts.a_risk_gold import generate

from .b_process import IsolatedB
from .risk_summary import summarize
from .run_dev import COST_LEDGER, CONTRACT, git_head, prior_paid_cost

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "var/risk_runs"
OUT_ROOT = ROOT / "artifacts/risk_runs"
BUDGET_FILE = ROOT / "var/real_run/risk_budget.json"
VAR_CONFIG = ROOT / "var/real_run/config.json"
PREREG = ROOT / "docs/decisions/RISK_TASKS_V2_PREREG.md"
TASK_SOURCES = ("sandbox/risk_tasks.py", "sandbox/risk_tasks_hard.py", "scripts/a_risk_gold.py")
TASK_SETS = {"v1": (FAMILIES, DEFAULT_SEED, select_risk_tasks), "v2": (HARD_FAMILIES, HARD_SEED, select_hard_tasks)}
PROFILES = ("P0", "P1", "P2")
FINISHED = frozenset({"completed", "truncated"})
# Stop launching new paid runs once less than this is left of the allowance.
RUN_RESERVE_CNY = 0.2
# A provider that keeps failing is out of quota or down; the rest of the batch waits for --resume.
PROVIDER_FAILURE_LIMIT = 6


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_source(explicit: str | None) -> Path:
    candidates = [explicit, os.environ.get(DB_ENV)]
    if VAR_CONFIG.is_file():
        candidates.append(json.loads(VAR_CONFIG.read_text(encoding="utf-8")).get("source_db"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise SystemExit(f"B-SCALE source is not configured: set {DB_ENV} or var/real_run/config.json")


def load_budget() -> dict:
    if not BUDGET_FILE.is_file():
        raise SystemExit("No approved risk-experiment budget (var/real_run/risk_budget.json); paid runs stay off.")
    return json.loads(BUDGET_FILE.read_text(encoding="utf-8"))


def authorize_paid(allowance: float) -> dict:
    """Paid calls need an approved budget, an explicit per-batch allowance and a key on this machine."""
    budget = load_budget()
    left = budget["approved_cny"] - budget["spent_cny"]
    if allowance <= 0 or allowance > left + 1e-9:
        raise SystemExit(f"Allowance {allowance} exceeds what is left of the approved budget ({left:.4f}).")
    prior, known = prior_paid_cost()
    if not known:
        raise SystemExit("Earlier paid cost is unknown; refusing to run blind.")
    # Process hard cap = what was already spent + this batch's allowance. B never receives these.
    os.environ["C_ENABLE_PAID_RUNS"] = "true"
    os.environ["C_MAX_COST_CNY"] = str(round(prior + allowance, 6))
    return budget


class CostGuard:
    def __init__(self, allowance: float | None):
        self.allowance = allowance
        self.spent = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.provider_failures = 0
        self.lock = threading.Lock()

    def remaining(self) -> float | None:
        with self.lock:
            return None if self.allowance is None else self.allowance - self.spent

    def add(self, cost: float | None, prompt: int, completion: int) -> None:
        with self.lock:
            self.spent += cost or 0.0
            self.prompt_tokens += prompt
            self.completion_tokens += completion

    def note_provider(self, failed: bool) -> None:
        with self.lock:
            self.provider_failures = self.provider_failures + 1 if failed else 0

    def provider_down(self) -> bool:
        with self.lock:
            return self.provider_failures >= PROVIDER_FAILURE_LIMIT


def request_of(fixture_id: str) -> tuple[str, str]:
    matched = RISK_FIXTURE_RE.fullmatch(fixture_id)
    return matched.group(1), matched.group(2)


def sources_sha256() -> str:
    digest = hashlib.sha256()
    for name in TASK_SOURCES:
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def write_gz(path: Path, value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    with gzip.open(path, "wb") as handle:
        handle.write(raw)
    return hashlib.sha256(raw).hexdigest()


def run_cell(cell, *, attempt, config, specs, b, raw_dir, guard, contract, experiment_id, source) -> dict:
    fixture_id, profile = cell
    family, request_id = request_of(fixture_id)
    row = {"fixture_id": fixture_id, "family": family, "request_id": request_id, "control_profile": profile,
           "config_id": config["config_id"], "attempt": attempt, "run_status": "scheduled", "loss_status": None,
           "net_loss_cents": None, "policy_compliance": None, "rejected_codes": []}
    if guard.provider_down():
        return row | {"run_status": "not_started", "stop_reason": "provider_unavailable"}
    remaining = guard.remaining()
    if remaining is not None and remaining < RUN_RESERVE_CNY:
        return row | {"run_status": "not_started", "stop_reason": "batch_allowance_exhausted"}
    adapter, budget, pricing, _ = build(config)
    admin = AdminTransport(b.base_url, b.admin_token, timeout=30)
    created = admin.create_session({"tenant_id": "risk-experiment", "fixture_id": fixture_id, "experiment_id": experiment_id,
                                    "config_id": config["config_id"], "execution_source": adapter.execution_source,
                                    "control_profile": profile})
    if created.http_status != 201:
        return row | {"run_status": "infra_error", "stop_reason": f"create_session_http_{created.http_status}"}
    info, token = created.payload["session"], created.payload["session_token"]
    session = SessionTransport(b.base_url, info["session_id"], token)
    del token
    run_dir = raw_dir / f"{profile}_{fixture_id}_a{attempt}"
    run_dir.mkdir(parents=True)
    log = AttemptLog(run_dir / "attempts.jsonl")
    log.record("episode_start", session_id=info["session_id"], config_id=config["config_id"], control_profile=profile,
               adapter=adapter.describe())
    try:
        result, transcript = run_episode(adapter, session, log, system_prompt=config["_prompt_text"],
                                         kickoff=config["kickoff"], tool_specs=specs[profile], budget=budget,
                                         pricing=pricing, run_tag=secrets.token_hex(4), remaining_cost_cny=remaining)
        episode = result.to_dict()
    except Exception as error:  # Infrastructure failure is a recorded outcome, not a silent skip.
        log.record("runner_exception", error_type=type(error).__name__)
        episode, transcript = {"run_status": "infra_error", "stop_reason": "runner_exception:" + type(error).__name__,
                               "trace": traceback.format_exc()[-1500:]}, []
    guard.add(episode.get("cost_cny") if adapter.paid else 0.0, episode.get("prompt_tokens") or 0, episode.get("completion_tokens") or 0)
    guard.note_provider(str(episode.get("stop_reason") or "").startswith("provider_"))
    write_gz(run_dir / "transcript.json.gz", transcript)
    row.update({key: episode.get(key) for key in ("run_status", "stop_reason", "turns", "tool_calls_dispatched", "local_rejections",
                                                  "prompt_tokens", "completion_tokens", "cost_cny", "elapsed_s")})
    exported = admin.evidence(info["session_id"])
    if exported.http_status != 200:
        return row | {"evidence_export": f"http_{exported.http_status}"}
    evidence = exported.payload
    wire.EvidenceBundle.model_validate(evidence)
    evidence_sha = write_gz(run_dir / "evidence.json.gz", evidence)
    # Gold is built only here, after the episode ended, and only from pre-execution facts.
    spec = generate(fixture_id, source)
    loss = evaluate_evidence(evidence, spec, evidence_sha)
    claim = calculate_claim(claim_event(loss), contract)
    write_gz(run_dir / "loss_result.json.gz", loss)
    rejected = [event["error"]["code"] for event in evidence["events"]
                if event["tool_name"] == "submit_refund" and event["status"] == "rejected" and event["error"]]
    due = sum(row_["legally_due_cents"] or 0 for row_ in spec["obligations"])
    row.update(task_outcome=loss["task_outcome"], committed_cents=loss["total_committed_cents"], due_cents=due,
               extra_cents=loss["total_extra_cents"], underpaid_cents=loss["total_underpaid_cents"],
               net_loss_cents=loss["net_loss_cents"], loss_status=loss["loss_status"],
               policy_compliance=loss["policy_compliance"], refund_attempts=loss["activity"]["write_succeeded"] + loss["activity"]["write_rejected"],
               rejected_codes=rejected, tickets=loss["activity"]["human_review_tickets"],
               ledger_issues=loss["ledger_checks"]["issues"], coverage_status=spec["coverage_status_input"],
               claim_status=claim["claim_status"], payout_cents=claim["payout_cents"], evidence_sha256=evidence_sha,
               execution_source=adapter.execution_source, counts_as_formal_run=False)
    return row


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--per-family", type=int, required=True)
    parser.add_argument("--profiles", default="P0,P1,P2")
    parser.add_argument("--task-set", choices=sorted(TASK_SETS), default="v1")
    parser.add_argument("--families", help="Comma-separated; default is every family of the task set")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", help="Default is the seed of the task set")
    parser.add_argument("--prefix", default="risk")
    parser.add_argument("--source-db")
    parser.add_argument("--paid", action="store_true")
    parser.add_argument("--allowance-cny", type=float)
    parser.add_argument("--resume", help="Existing batch id; reruns only cells that never finished")
    args = parser.parse_args(argv)

    source = resolve_source(args.source_db)
    os.environ[DB_ENV] = str(source)
    config = load_config(ROOT / args.config)
    profiles = [value for value in args.profiles.split(",") if value]
    if set(profiles) - set(PROFILES):
        raise SystemExit("Unknown control profile")
    guard = CostGuard(None)
    budget_record = None
    if config["adapter"] == "openai_compatible":
        if not args.paid or args.allowance_cny is None:
            raise SystemExit("A real model needs --paid and --allowance-cny.")
        budget_record = authorize_paid(args.allowance_cny)
        guard = CostGuard(args.allowance_cny)

    families, default_seed, select_tasks = TASK_SETS[args.task_set]
    args.seed = args.seed or default_seed
    wanted = set(args.families.split(",")) if args.families else set(families)
    tasks = [fid for fid in select_tasks(source, args.per_family, args.seed) if request_of(fid)[0] in wanted]
    cells = [(fixture_id, profile) for fixture_id in tasks for profile in profiles]
    # A shuffled order keeps a batch balanced across arms if the allowance stops it early.
    random.Random(args.seed).shuffle(cells)

    batch_id = args.resume or f"{args.prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out_dir = OUT_ROOT / batch_id
    raw_dir = RAW_ROOT / batch_id
    out_dir.mkdir(parents=True, exist_ok=bool(args.resume))
    raw_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    attempts: dict[tuple[str, str], int] = {}
    done: set[tuple[str, str]] = set()
    previous: list[dict] = []
    if results_path.exists():
        previous = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line]
        for row in previous:
            key = (row["fixture_id"], row["control_profile"])
            attempts[key] = max(attempts.get(key, 0), row["attempt"])
            if row["run_status"] in FINISHED:
                done.add(key)
    todo = [cell for cell in cells if cell not in done]
    specs = {profile: model_tool_specs(profile) for profile in PROFILES}
    manifest = {"batch_id": batch_id, "started_at": now(), "config_id": config["config_id"], "config_sha256": config["_sha256"],
                "prompt_version": config["prompt_version"], "prompt_sha256": config["_prompt_sha256"],
                "tool_specs_sha256": {profile: tool_specs_sha256(spec) for profile, spec in specs.items()},
                "task_set": args.task_set, "task_source_sha256": sources_sha256(),
                "prereg_sha256": hashlib.sha256(PREREG.read_bytes()).hexdigest() if args.task_set == "v2" else None,
                "profiles": profiles, "families": sorted(wanted), "per_family": args.per_family, "seed": args.seed,
                "tasks": len(tasks), "cells": len(cells), "workers": args.workers, "runner_version": RUNNER_VERSION,
                "contract_version": wire.VERSION, "git_head": git_head(), "paid": bool(budget_record),
                "allowance_cny": args.allowance_cny if budget_record else None,
                "budget_approval": budget_record.get("approval") if budget_record else None,
                "counts_as_formal_run": False, "experiment_nature": "pressure test on synthetic tasks; not a natural accident rate"}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    write_lock = threading.Lock()
    finished = 0
    rows = list(previous)
    try:
        with IsolatedB(raw_dir / "b.sqlite3", raw_dir / f"b_server_{secrets.token_hex(3)}.log") as b, \
                results_path.open("a", encoding="utf-8") as results, ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run_cell, cell, attempt=attempts.get(cell, 0) + 1, config=config, specs=specs, b=b,
                                   raw_dir=raw_dir, guard=guard, contract=contract, experiment_id=batch_id, source=source): cell
                       for cell in todo}
            for future in as_completed(futures):
                row = future.result()
                with write_lock:
                    rows.append(row)
                    results.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    results.flush()
                    finished += 1
                if finished % 25 == 0 or finished == len(todo):
                    print(json.dumps({"finished": finished, "of": len(todo), "spent_cny": round(guard.spent, 4)}), flush=True)
    finally:
        if budget_record is not None and guard.spent > 0:
            COST_LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with COST_LEDGER.open("a", encoding="utf-8") as ledger:
                ledger.write(json.dumps({"recorded_at": now(), "run": f"risk_runs/{batch_id}", "config_id": config["config_id"],
                                         "prompt_tokens": guard.prompt_tokens, "completion_tokens": guard.completion_tokens,
                                         "cost_cny": round(guard.spent, 6), "cost_basis": config["pricing"]["basis"]}) + "\n")
            budget_record["spent_cny"] = round(budget_record["spent_cny"] + guard.spent, 6)
            BUDGET_FILE.write_text(json.dumps(budget_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = summarize([row for row in rows if row["run_status"] != "not_started"])
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("batch: " + batch_id)
    print(json.dumps(summary["arms"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
