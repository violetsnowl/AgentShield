# -*- coding: utf-8 -*-
"""网页启动的真实批次编排：采样 → 计划 → run_dev → A 自动 Gold（仓库外）→ 复核 → 最终文件。

- 全部复用现有组件：C Runner（experiments.run_dev）、B 沙箱进程、A5 自动 Gold、evaluator 复核；
  不引入新保险/Agent 算法，不修改 C 原始 LossResult。
- 付费调用只在 --paid 且预算批准记录存在、额度足够、本机 .env 已配置密钥时进行；
  免费 dry-run 用 rule-baseline 配置走通同一条链路（不含任何模型调用）。
- Gold 规格只写仓库外私有目录；本脚本不输出密钥；launch_paid_api 永不为 true。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluator.obligations import load_spec  # noqa: E402
from experiments.reverify_evidence import reverify  # noqa: E402
from experiments.run_dev import prior_paid_cost  # noqa: E402
from runners.env import load_runner_env  # noqa: E402
from sandbox.bscale_authorization import fixture_id_for, select_task_ids  # noqa: E402
from scripts.a_bscale_auto_gold_batch import main as gold_batch_main  # noqa: E402

RUNS_ROOT = ROOT / "artifacts/c_l0/runs"
CONTRACT = ROOT / "configs/insurance/research_contract_v0.1.json"
APPROVAL_PATH = ROOT / "var/real_run/approval.json"
VAR_CONFIG = ROOT / "var/real_run/config.json"
PER_RUN_CAP_CNY = 0.5
STAGE_CAPS = {1: 0.5, 5: 1.5}


class RealBatchError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def resolve_source(explicit: str | None) -> Path:
    candidates: list[str | None] = [explicit, os.environ.get("AGENTSHIELD_BSCALE_DB")]
    if VAR_CONFIG.is_file():
        try:
            candidates.append(json.loads(VAR_CONFIG.read_text(encoding="utf-8")).get("source_db"))
        except (OSError, ValueError):
            pass
    for candidate in candidates:
        if candidate:
            path = Path(candidate)
            if path.is_file() and path.suffix in {".db", ".sqlite", ".sqlite3"}:
                return path.resolve()
    raise RealBatchError("B-SCALE source database is not configured")


def requested_cap(count: int) -> float:
    return STAGE_CAPS.get(count, round(PER_RUN_CAP_CNY * count, 2))


def process_cap_for(allowance: float, prior: float) -> float:
    """增量口径：进程全局硬顶 = 既有台账支出 + 本轮新增额度。

    run_dev 会用「进程硬顶 − 台账累计」得到剩余额度，因此该组合保证：
    本轮新增花费恰好被封在 allowance 之内（超过即在回合间/回合内立即停止）。
    """
    return round(allowance + prior, 6)


def load_approval(path: Path | None = None) -> float | None:
    try:
        value = json.loads((path or APPROVAL_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    cap = value.get("active_cap_cny")
    if type(cap) not in (int, float) or cap <= 0:
        return None
    return float(cap)


def authorize_paid(cap: float | None, approved: float | None, env: dict[str, str]) -> float:
    """付费三查：有批准记录、额度不超批、密钥已在本机配置。返回本次进程全局上限。"""
    if approved is None:
        raise RealBatchError("no active budget approval (var/real_run/approval.json)")
    requested = float(cap) if cap is not None else None
    if requested is None or requested <= 0:
        raise RealBatchError("a positive process cap is required for paid runs")
    if requested > approved + 1e-9:
        raise RealBatchError(f"requested cap {requested} exceeds approved {approved}")
    if not env.get("DEEPSEEK_API_KEY"):
        raise RealBatchError("DEEPSEEK_API_KEY is not configured in the local .env")
    return requested


def ensure_private_dir(path: Path) -> Path:
    dest = path.resolve()
    if "git_ready" in dest.parts or any((parent / ".git").exists() for parent in (dest, *dest.parents)):
        raise RealBatchError("Gold directory must be outside the Git working tree")
    return dest


def build_plan(prefix: str, experiment_id: str, config_rel: str, request_ids: list[str]) -> dict:
    return {
        "batch_prefix": prefix,
        "experiment_id": experiment_id,
        "purpose": "Web-launched development batch on random B-SCALE tasks. Not a formal sample and not a commercial claim.",
        "status": "development",
        "counts_as_formal_run": False,
        "launch_paid_api": False,
        "runs": [
            {"label": "bscale_sim_" + rid.replace("-", "_"), "config": config_rel, "fixture_id": fixture_id_for(rid)}
            for rid in request_ids
        ],
    }


def chunked(items: list, size: int = 10):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def parse_run_line(line: str) -> dict | None:
    try:
        value = json.loads(line)
    except ValueError:
        return None
    return value if isinstance(value, dict) and "label" in value else None


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--prefix", default="bscale-web-deepseek")
    parser.add_argument("--config", default="configs/runner/deepseek-fixed-dev-v0.1.json")
    parser.add_argument("--paid", action="store_true")
    parser.add_argument("--cap", type=float, default=None)
    parser.add_argument("--status", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--gold-dir", required=True)
    parser.add_argument("--source-db", default=None)
    args = parser.parse_args(argv)
    if not 1 <= args.count <= 10:
        print(json.dumps({"error": "count must be between 1 and 10"}))
        return 2
    status_path = Path(args.status)
    work_dir = Path(args.work_dir)
    state: dict = {"batch_id": None, "prefix": args.prefix, "count": args.count, "seed": args.seed,
                   "stage": "starting", "runs": [], "batch_dir": None, "error": None,
                   "paid": bool(args.paid), "cap_cny": args.cap, "process_cap_cny": None, "prior_paid_cny": None,
                   "started_at": now(), "finished_at": None}

    def update(**kw) -> None:
        state.update(kw)
        write_json(status_path, state)

    try:
        cap = None
        process_cap = None
        if args.paid:
            cap = authorize_paid(args.cap, load_approval(), load_runner_env())
            prior, known = prior_paid_cost()
            if not known:
                raise RealBatchError("earlier paid cost unknown; refusing to exceed the stage allowance blindly")
            process_cap = process_cap_for(cap, prior)
        gold_dir = ensure_private_dir(Path(args.gold_dir))
        source = resolve_source(args.source_db)
        update(stage="sampling", paid=bool(args.paid), cap_cny=cap,
               process_cap_cny=process_cap, prior_paid_cny=(prior if args.paid else None))
        request_ids = select_task_ids(source, args.count, args.seed)
        job_dir = work_dir / (args.prefix + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3))
        update(request_ids=request_ids)
        plan = build_plan(args.prefix, job_dir.name, args.config, request_ids)
        plan_path = job_dir / "plan.json"
        write_json(plan_path, plan)
        write_json(job_dir / "request_ids.json", request_ids)
        child_env = dict(os.environ)
        child_env["AGENTSHIELD_BSCALE_DB"] = str(source)
        if args.paid:
            child_env["C_ENABLE_PAID_RUNS"] = "true"
            child_env["C_MAX_COST_CNY"] = str(process_cap)
        else:
            for key in ("C_ENABLE_PAID_RUNS", "C_MAX_COST_CNY"):
                child_env.pop(key, None)
        update(stage="running")
        log_path = job_dir / "run_dev.log"
        code = 1
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "experiments.run_dev", "--plan", str(plan_path)],
                cwd=ROOT, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace")
            assert process.stdout is not None
            for line in process.stdout:
                log.write(line)
                log.flush()
                stripped = line.strip()
                if stripped.startswith("batch:"):
                    # run_dev 自行派生批次目录名；以其输出为权威（预判秒差会错位）。
                    relative = stripped.split("batch:", 1)[1].strip()
                    state["batch_id"] = Path(relative).name
                    state["batch_dir"] = relative
                    write_json(status_path, state)
                    continue
                record = parse_run_line(line)
                if record is not None:
                    state["runs"].append({key: record.get(key) for key in
                                          ("label", "run_status", "stop_reason", "task_outcome",
                                           "total_committed_cents", "loss_status", "net_loss_cents",
                                           "claim_status", "cost_cny")})
                    write_json(status_path, state)
            code = process.wait()
        if code != 0:
            raise RealBatchError(f"run_dev exited with {code}")
        if not state["batch_id"]:
            candidates = sorted((path for path in RUNS_ROOT.glob(args.prefix + "-*") if path.is_dir()),
                                key=lambda path: path.stat().st_mtime, reverse=True)
            if candidates:
                state["batch_id"] = candidates[0].name
                state["batch_dir"] = f"artifacts/c_l0/runs/{candidates[0].name}"
        batch_dir = RUNS_ROOT / str(state["batch_id"]) if state["batch_id"] else None
        if batch_dir is None or not batch_dir.is_dir():
            raise RealBatchError("batch directory missing after run")
        update(stage="verifying", batch_dir=f"artifacts/c_l0/runs/{state['batch_id']}")

        gold_out = gold_dir / str(state["batch_id"])
        ids_file = job_dir / "request_ids.json"
        merged_cases: list = []
        for index, chunk in enumerate(chunked(list(request_ids), 10)):
            chunk_file = job_dir / f"request_ids_chunk_{index}.json"
            write_json(chunk_file, chunk)
            if gold_batch_main(["--source-db", str(source), "--request-ids-file", str(chunk_file),
                                "--out-private-dir", str(gold_out)]) != 0:
                raise RealBatchError("auto Gold generation failed")
            manifest = json.loads((gold_out / "PRIVATE_manifest.json").read_text(encoding="utf-8"))
            merged_cases.extend(manifest.get("cases", []))
        write_json(gold_out / "PRIVATE_manifest.json",
                   {"scope": "private_A_to_C_after_execution_only", "cases": merged_cases})

        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        final_runs: list = []
        for entry in state["runs"]:
            label = entry["label"]
            run_dir = batch_dir / label
            rid = label.split("_", 1)[1].removeprefix("bscale_sim_").replace("_", "-")
            spec_path = gold_out / f"obligation_{rid}.json"
            final = dict(entry)
            if not run_dir.is_dir():
                final["verify_note"] = "run directory missing"
            elif not spec_path.is_file():
                final["verify_note"] = "gold spec missing; kept runner pre-gold result"
            elif (run_dir / "evidence.json").is_file():
                raw = (run_dir / "evidence.json").read_bytes()
                evidence = json.loads(raw.decode("utf-8"))
                loss, claim = reverify(evidence, load_spec(spec_path), contract,
                                       hashlib.sha256(raw).hexdigest())
                for name, alias in (("loss_result.json", "loss_result_before_gold.json"),
                                    ("claim_A0.json", "claim_A0_before_gold.json")):
                    target = run_dir / name
                    if target.is_file() and not (run_dir / alias).exists():
                        (run_dir / alias).write_bytes(target.read_bytes())
                write_json(run_dir / "post_obligation" / "loss_result.json", loss)
                write_json(run_dir / "post_obligation" / "claim_A0.json", claim)
                write_json(run_dir / "loss_result.json", loss)
                write_json(run_dir / "claim_A0.json", claim)
                final.update(loss_status=loss["loss_status"], net_loss_cents=loss["net_loss_cents"],
                             claim_status=claim["claim_status"], payout_cents=claim["payout_cents"])
            final_runs.append(final)
        update(stage="completed", runs=final_runs, finished_at=now())
        print(json.dumps({"batch_id": state["batch_id"], "stage": "completed", "runs": len(final_runs),
                          "batch_dir": state["batch_dir"]}, ensure_ascii=False))
        return 0
    except Exception as error:  # 记录而非静默：失败态写入状态文件。
        update(stage="failed", error=f"{type(error).__name__}: {error}", finished_at=now())
        print(json.dumps({"error": state["error"]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
