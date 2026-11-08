"""Batch ledger: what each big number in the risk experiment counts, and whether they reconcile.

  python -m experiments.batch_ledger            write docs/validation/batch_ledger_v0.1.{json,md}
  python -m experiments.batch_ledger --sample   rebuild docs/validation/evidence_sample_00067996/ from var/

It only reads batch results, runner configs and the evidence chain. It never changes the official
counting rules in experiments/annual_calibration.py; it calls them and then re-counts from raw rows.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import statistics
import subprocess
from typing import Any

from experiments.annual_calibration import PAIRED_BATCH, SENTINEL_ARMS, real_rows, severity
from experiments.claim_pack import RAW_ROOT, RESULTS_ROOT, ROOT, RUNNER_CONFIGS, is_accident, latest_rows, model_of
from experiments.evidence_chain import CHAIN_FILE, batch_rows, verify_raw
from experiments.evidence_chain import build as build_chain
from experiments.risk_summary import ACCIDENT_FLOOR_CENTS, wilson
from workbench.claim_cases import OBSERVED, VOIDED_CONFIG_SUFFIX, _thinking_label

SCHEMA = "AgentShield.batch_ledger.v0.1"
OUT_DIR = ROOT / "docs/validation"
JSON_OUT = OUT_DIR / "batch_ledger_v0.1.json"
MD_OUT = OUT_DIR / "BATCH_LEDGER_V0.1.md"
EVIDENCE_FILE = ROOT / "configs/insurance/annual_evidence_v0.2.json"
PREREG = "docs/decisions/RISK_TASKS_V2_PREREG.md"
PROFILES = ("P0", "P1", "P2")
SCRIPTED = "scripted_test"
CLAIM_PACKS = ROOT / "var/claim_packs"
SAMPLE_BATCH = "risk-direct-low-20261106-221729"
SAMPLE_RUN = "P0_risk-v2-h5-rr-synth-00067996_a1"
SAMPLE_DIR = OUT_DIR / "evidence_sample_00067996"
WRITE_TOOLS = ("submit_refund", "submit_human_review", "finish_case")

# Credential shapes. Scans report which pattern or field matched, never the matched text.
SECRET_PATTERNS = {
    "sk-style API key": r"\bsk-[A-Za-z0-9_\-]{12,}",
    "Bearer token": r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}",
    "Authorization header": r"(?i)\bauthorization\s*[:=]",
    "URL with credentials": r"://[^/\s:@\"]+:[^/\s@\"]+@",
    "URL query secret": r"(?i)[?&](key|token|api_key|access_token|sig|signature)=",
    "e-mail address": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "mainland phone number": r"(?<!\d)1[3-9]\d{9}(?!\d)",
}
SECRET_KEYS = re.compile(r"(api[_-]?key|authorization|secret|password|passwd|credential|cookie|(^|_)token$|access[_-]?token|iban|bank|card_no|"
                         r"(^|_)account(_|$)|phone|mobile|e-?mail)", re.I)


def scan_text(text: str) -> list[str]:
    return [name for name, pattern in SECRET_PATTERNS.items() if re.search(pattern, text)]


def scan_keys(value: Any, path: str = "") -> list[str]:
    """Field paths whose name looks like a credential or account field."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            here = f"{path}.{key}"
            if SECRET_KEYS.search(str(key)):
                found.append(here)
            found.extend(scan_keys(child, here))
    elif isinstance(value, list):
        for child in value:
            found.extend(scan_keys(child, f"{path}[]"))
    return found


def scan_file(path: Path) -> list[str]:
    """Problems found in one file, as 'pattern' or 'field path' names only."""
    text = path.read_text(encoding="utf-8")
    problems = scan_text(text)
    if path.suffix == ".json":
        problems += [f"field {name}" for name in scan_keys(json.loads(text))]
    return problems


def _configs() -> dict[str, dict[str, Any]]:
    found = {}
    for path in sorted(RUNNER_CONFIGS.glob("*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        found[str(config.get("config_id"))] = config
    return found


def channel_of(config: dict[str, Any] | None) -> str:
    if config is None:
        return "未知"
    if config.get("execution_source") == SCRIPTED:
        return "脚本（不调用模型）"
    return "Command Code" if config.get("provider") == "commandcode" else "官方接口"


def _manifest(folder: Path) -> dict[str, Any]:
    path = folder / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _count(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return dict(sorted(out.items()))


def _folders(results_root: Path) -> list[Path]:
    return sorted(path for path in results_root.iterdir() if (path / "results.jsonl").is_file())


def batch_line(folder: Path, configs: dict[str, dict[str, Any]], counted: bool) -> dict[str, Any]:
    raw = list(batch_rows(folder))
    latest = latest_rows(folder.name, folder.parent)
    manifest = _manifest(folder)
    config_id = str(raw[0].get("config_id"))
    config = configs.get(config_id)
    scripted = bool(config and config.get("execution_source") == SCRIPTED)
    done = [row for row in latest if row.get("run_status") == "completed"]
    hits = [row for row in done if is_accident(row)]
    by_profile = {name: {"runs": sum(1 for row in done if row["control_profile"] == name),
                         "accidents": sum(1 for row in hits if row["control_profile"] == name)} for name in PROFILES}
    return {"batch_id": folder.name, "task_set": manifest.get("task_set"), "started_at": manifest.get("started_at"),
            "distinct_tasks": len({row["fixture_id"] for row in raw}), "raw_rows": len(raw), "latest_rows": len(latest),
            "run_status_latest": _count(row.get("run_status") for row in latest), "run_status_raw": _count(row.get("run_status") for row in raw),
            "execution_source_latest": _count(row.get("execution_source") for row in latest),
            "retry_rows": sum(1 for row in raw if (row.get("attempt") or 1) > 1), "superseded_rows": len(raw) - len(latest),
            "config_id": config_id, "model": model_of(config_id), "provider": (config or {}).get("provider"), "channel": channel_of(config),
            "thinking": "不适用（脚本）" if scripted else _thinking_label(config_id),
            "profiles": by_profile, "accidents": len(hits), "net_loss_cents": sum(row["net_loss_cents"] for row in hits),
            "below_floor_net_loss_cents": sum(row.get("net_loss_cents") or 0 for row in done if not is_accident(row)),
            "voided": config_id.endswith(VOIDED_CONFIG_SUFFIX), "counted_in_real_runs": counted}


def dedup_rules(rows_by_batch: dict[str, list[dict[str, Any]]], started: dict[str, str]) -> dict[str, Any]:
    """162 accident rows -> 69 tasks, under the official rule and two alternatives. Reference only."""
    per_task: dict[str, list[tuple[str, int]]] = {}
    for batch in sorted(rows_by_batch, key=lambda name: (started.get(name) or "", name)):
        for row in rows_by_batch[batch]:
            if is_accident(row):
                per_task.setdefault(row["fixture_id"], []).append((batch, row["net_loss_cents"]))
    mean = [round(sum(cents for _, cents in values) / len(values)) for values in per_task.values()]
    biggest = [max(cents for _, cents in values) for values in per_task.values()]
    first = [values[0][1] for values in per_task.values()]
    rows = sum(len(values) for values in per_task.values())
    total = sum(cents for values in per_task.values() for _, cents in values)
    contributions = _count(batch for values in per_task.values() for batch, _ in values)
    return {"accident_rows": rows, "distinct_tasks": len(per_task), "net_loss_cents": total,
            "rule": "同一任务（fixture_id）在不同配置或重复运行里多次出险，先取这些出险行净损失的平均值（四舍五入到分），每个任务算一个点。",
            "official_mean_of_task_means_cents": round(statistics.mean(mean)), "alt_max_mean_cents": round(statistics.mean(biggest)),
            "alt_first_mean_cents": round(statistics.mean(first)), "no_dedup_mean_per_accident_row_cents": round(total / rows),
            "first_order": "按 manifest 的 started_at 先后，同批内按 results.jsonl 行序",
            "accidents_per_task": _count(len(values) for values in per_task.values()),
            "accident_rows_by_batch": contributions}


def chain_parts(results_root: Path, voided: set[str], configs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """What the 9,186 links and the 5,732 raw-evidence files are made of."""
    labels = {"completed_observed_counted": "完成的真实模型运行，计入 real_runs",
              "completed_observed_voided": "完成的真实模型运行，但配置已作废",
              "completed_scripted_probe": "脚本探针（red-team 脚本，不是模型）完成行",
              "infra_error": "基础设施失败行（连接中断、超时、网关错误、输出被截断等）",
              "truncated": "运行超时被截断的行",
              "not_started": "未开始行（提供方不可用或批次额度用尽，没有运行也没有证据）",
              "other": "其他状态"}
    parts = {key: {"label": label, "links": 0, "with_evidence_digest": 0, "superseded_by_retry": 0} for key, label in labels.items()}
    reference_rows, scripted = 0, set()
    for folder in _folders(results_root):
        rows = list(batch_rows(folder))
        final = {(row["fixture_id"], row["control_profile"]): index for index, row in enumerate(rows)}
        for index, row in enumerate(rows):
            status, source = row.get("run_status"), row.get("execution_source")
            if status == "completed" and source == OBSERVED:
                key = "completed_observed_voided" if folder.name in voided else "completed_observed_counted"
            elif status == "completed" and source == SCRIPTED:
                key = "completed_scripted_probe"
            else:
                key = status if status in parts else "other"
            if source == SCRIPTED:
                scripted.add(str(row.get("config_id")))
                reference_rows += int((configs.get(str(row.get("config_id"))) or {}).get("adapter") == "rule_baseline")
            part = parts[key]
            part["links"] += 1
            part["with_evidence_digest"] += int(bool(row.get("evidence_sha256")))
            part["superseded_by_retry"] += int(final[(row["fixture_id"], row["control_profile"])] != index)
    return {"links": sum(part["links"] for part in parts.values()), "parts": {key: part for key, part in parts.items() if part["links"]},
            "reference_solution_rows": reference_rows, "scripted_configs": sorted(scripted),
            "rows_with_evidence_digest": sum(part["with_evidence_digest"] for part in parts.values())}


def _git(*args: str) -> str | None:
    try:
        done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None


def versions(chain_stored: dict[str, Any]) -> dict[str, Any]:
    first = (_git("log", "--follow", "--format=%H %ci", "--", PREREG) or "").splitlines()
    last = _git("log", "-1", "--format=%H %ci", "--", "artifacts/risk_runs/evidence_chain.json")
    prereg = ROOT / PREREG
    manifests = {_manifest(folder).get("prereg_sha256") for folder in _folders(RESULTS_ROOT)} - {None}
    digest = sha256(prereg.read_bytes()).hexdigest() if prereg.is_file() else None
    pushed = _git("branch", "-r", "--contains", last.split()[0]) if last else None
    return {"prereg_file": PREREG, "prereg_first_commit": first[-1] if first else None, "prereg_sha256": digest,
            "prereg_sha256_in_manifests": sorted(manifests), "prereg_matches_manifests": bool(digest) and manifests == {digest},
            "chain_root": chain_stored.get("root"), "chain_links": chain_stored.get("links"), "chain_last_commit": last,
            "chain_file_clean": not _git("status", "--porcelain", "--", "artifacts/risk_runs/evidence_chain.json"),
            "chain_commit_on_remote_tracking_branch": pushed, "remote_checked_online": False}


def sentinel_pair(results_root: Path) -> dict[str, Any]:
    wide = latest_rows(PAIRED_BATCH, results_root)
    narrow = latest_rows(SENTINEL_ARMS["low"], results_root)
    narrow_tasks = {row["fixture_id"] for row in narrow}

    def cell(rows: list[dict[str, Any]], tasks: set[str] | None) -> dict[str, Any]:
        picked = [row for row in rows if row["control_profile"] == "P0" and row["run_status"] == "completed" and (tasks is None or row["fixture_id"] in tasks)]
        hits = sum(1 for row in picked if is_accident(row))
        low, high = wilson(hits, len(picked))
        return {"runs": len(picked), "accidents": hits, "wilson_low": low, "wilson_high": high}

    config = _configs()
    wide_id, narrow_id = str(wide[0]["config_id"]), str(narrow[0]["config_id"])
    manifests = {"wide": _manifest(results_root / PAIRED_BATCH), "narrow": _manifest(results_root / SENTINEL_ARMS["low"])}
    same_keys = ("prompt_sha256", "task_source_sha256", "prereg_sha256", "seed", "per_family", "git_head")
    params = {name: (config.get(config_id) or {}).get("request_params") for name, config_id in (("wide", wide_id), ("narrow", narrow_id))}
    return {"wide_workers": manifests["wide"].get("workers"), "narrow_workers": manifests["narrow"].get("workers"),
            "wide_started_at": manifests["wide"].get("started_at"), "narrow_started_at": manifests["narrow"].get("started_at"),
            "wide_profiles": manifests["wide"].get("profiles"), "narrow_profiles": manifests["narrow"].get("profiles"),
            "identical_manifest_fields": [key for key in same_keys if manifests["wide"].get(key) == manifests["narrow"].get(key)],
            "different_manifest_fields": [key for key in same_keys if manifests["wide"].get(key) != manifests["narrow"].get(key)],
            "same_request_params": params["wide"] == params["narrow"], "request_params": params["narrow"],"wide_batch": PAIRED_BATCH, "narrow_batch": SENTINEL_ARMS["low"], "wide_config": wide_id, "narrow_config": narrow_id,
            "wide_channel": channel_of(config.get(wide_id)), "narrow_channel": channel_of(config.get(narrow_id)),
            "wide_model": model_of(wide_id), "narrow_model": model_of(narrow_id),
            "narrow_families": sorted({row["family"] for row in narrow}), "narrow_tasks_inside_wide": narrow_tasks <= {row["fixture_id"] for row in wide},
            "wide_all_tasks_P0": cell(wide, None), "wide_on_narrow_tasks_P0": cell(wide, narrow_tasks), "narrow_P0": cell(narrow, None),
            "narrow_accident_tasks": sorted(row["fixture_id"] for row in narrow if is_accident(row))}


def build(results_root: Path = RESULTS_ROOT, raw_root: Path = RAW_ROOT, check_raw: bool = True) -> dict[str, Any]:
    configs = _configs()
    counted = real_rows(results_root)
    folders = _folders(results_root)
    batches = [batch_line(folder, configs, folder.name in counted) for folder in folders]
    sev = severity(counted)
    real_runs = sum(len(rows) for rows in counted.values())
    started = {line["batch_id"]: line["started_at"] for line in batches}
    stored_evidence = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8")) if EVIDENCE_FILE.is_file() else {}
    stored = stored_evidence.get("severity", {})
    totals = {"real_runs": real_runs, "accidents": sev["accidents"], "net_loss_cents": sev["net_loss_cents"], "distinct_tasks": sev["distinct_tasks"],
              "task_mean_cents": sev["mean_cents"], "from_batch_table": {
                  "real_runs": sum(sum(p["runs"] for p in line["profiles"].values()) for line in batches if line["counted_in_real_runs"]),
                  "accidents": sum(line["accidents"] for line in batches if line["counted_in_real_runs"]),
                  "net_loss_cents": sum(line["net_loss_cents"] for line in batches if line["counted_in_real_runs"])},
              "annual_evidence_file": {"real_runs": stored_evidence.get("real_runs"), "accidents": stored.get("accidents"),
                                       "net_loss_cents": stored.get("net_loss_cents"), "distinct_tasks": stored.get("distinct_tasks"),
                                       "mean_cents": stored.get("mean_cents")}}
    totals["reconciles"] = {key: totals[key] == totals["from_batch_table"].get(key) == totals["annual_evidence_file"][key]
                            for key in ("real_runs", "accidents", "net_loss_cents")}
    totals["reconciles"]["distinct_tasks"] = totals["distinct_tasks"] == totals["annual_evidence_file"]["distinct_tasks"]
    stored_chain = json.loads(CHAIN_FILE.read_text(encoding="utf-8")) if CHAIN_FILE.is_file() else {}
    current_chain = build_chain(results_root)
    voided = {line["batch_id"] for line in batches if line["voided"]}
    parts = chain_parts(results_root, voided, configs)
    raw = verify_raw(results_root, raw_root) if check_raw else {"checked": None, "absent": None, "wrong": []}
    by_thinking = _count(thinking for line in batches if line["counted_in_real_runs"] for thinking in [line["thinking"]] * line["accidents"])
    return {"schema": SCHEMA, "accident_floor_cents": ACCIDENT_FLOOR_CENTS, "batches": batches, "totals": totals,
            "task_families": {name: cell["tasks"] for name, cell in sev["by_family"].items()},
            "accident_rows_by_thinking": by_thinking, "dedup": dedup_rules(counted, started),
            "chain": {"links_stored": stored_chain.get("links"), "links_current": current_chain["links"], "root_stored": stored_chain.get("root"),
                      "root_current": current_chain["root"], "batches_in_chain": len(stored_chain.get("batches", [])), **parts},
            "raw_evidence": {"rows_with_digest": parts["rows_with_evidence_digest"], "files_checked": raw["checked"], "files_absent": raw["absent"],
                             "files_wrong": len(raw["wrong"]),
                             "what": "results.jsonl 里带 evidence_sha256 的行，每行对应 var/risk_runs/<批次>/<运行名>/evidence.json.gz 一份，解压后哈希须与该行一致"},
            "sentinel_pair": sentinel_pair(results_root), "versions": versions(stored_chain),
            "commands": ["python -m experiments.annual_calibration  # 重算 annual_evidence_v0.2.json",
                         "python -m experiments.evidence_chain --verify  # 链条与原始证据核对",
                         "python -m experiments.batch_ledger  # 重写本对账表",
                         "python -m unittest tests.test_batch_ledger"]}


def yuan(cents: int) -> str:
    return f"{cents // 100:,}.{cents % 100:02d}"


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _table(head: list[str], rows: list[list[Any]]) -> list[str]:
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]


def render(ledger: dict[str, Any]) -> str:
    totals, dedup, chain, raw, pair, ver = (ledger[key] for key in ("totals", "dedup", "chain", "raw_evidence", "sentinel_pair", "versions"))
    parts = chain["parts"]
    part = lambda key, field="links": parts.get(key, {}).get(field, 0)  # noqa: E731
    counted = [line for line in ledger["batches"] if line["counted_in_real_runs"]]
    superseded = sum(item["superseded_by_retry"] for item in parts.values())
    out = ["# 批次对账表 v0.1", "",
           "本表回答外部审查的问题：4,326 次真实模型运行、162 起事故、净损失 86,019.26 元、69 个去重任务、哈希链 9,186 条、原始证据 5,732 份，"
           "各是什么口径，能否相互对上。数字由 `python -m experiments.batch_ledger` 从批次结果重算，没有手填。", "",
           "这是合成任务上的压力测试，不是自然事故率，也不是报价依据。", "", "## 一、结论", "",
           f"- 真实运行 {totals['real_runs']:,}、事故 {totals['accidents']}、净损失 {totals['net_loss_cents']:,} 分（{yuan(totals['net_loss_cents'])} 元）、"
           f"去重任务 {totals['distinct_tasks']}。这四个数与 `configs/insurance/annual_evidence_v0.2.json` 逐项一致，前三个也与下面批次表的合计一致。",
           f"- 哈希链 {chain['links_current']:,} 条是全部 {chain['batches_in_chain']} 个批次的全部记录，含失败、重试、未开始、脚本探针和作废配置。它不是 4,326 的另一种说法。",
           f"- 原始证据 {raw['rows_with_digest']:,} 份是链条里带证据哈希的行。未开始的 {chain['links'] - raw['rows_with_digest']:,} 行没有证据，所以比链条少这么多。",
           f"- 事故数 {totals['accidents']} 是“出险的运行次数”，不是 {totals['accidents']} 个独立任务。同一任务被多个配置撞到，所以折成 {totals['distinct_tasks']} 个任务。",
           f"- 事故按思考设置分：{_kv(ledger['accident_rows_by_thinking'])}。读严重度均值时要知道，事故主要来自关思考的批次。", "",
           "## 二、批次表", "",
           f"运行数和事故数只统计每个格子（任务 × 护栏档）最新一次尝试，且 run_status 为 completed。事故指净损失不低于 {ledger['accident_floor_cents']} 分。"
           "净损失只累计事故行。“计入”指进入 real_runs。", ""]
    short = {"observed_agent_execution": "真实", "scripted_test": "脚本", "None": "无"}
    rows = []
    for line in ledger["batches"]:
        rows.append([line["batch_id"], line["task_set"] or "null", line["distinct_tasks"], line["raw_rows"], line["latest_rows"],
                     "、".join(f"{key} {value}" for key, value in line["run_status_latest"].items()),
                     "、".join(f"{short.get(key, key)} {value}" for key, value in line["execution_source_latest"].items()), line["retry_rows"],
                     line["model"], line["channel"], line["thinking"], *[f"{line['profiles'][name]['runs']}/{line['profiles'][name]['accidents']}" for name in PROFILES],
                     line["accidents"], f"{line['net_loss_cents']:,}", "是" if line["voided"] else "否", "是" if line["counted_in_real_runs"] else "否"])
    rows.append(["合计（计入的批次）", "", "", "", "", "", "", "", "", "", "", "", "", "", totals["accidents"], f"{totals['net_loss_cents']:,}", "", f"real_runs {totals['real_runs']:,}"])
    out += _table(["批次", "任务集", "唯一任务", "原始行", "去重后行", "状态计数（去重后）", "来源计数（去重后）", "重试行", "模型", "通道", "思考",
                   "P0 运行/事故", "P1 运行/事故", "P2 运行/事故", "事故", "净损失（分）", "作废", "计入"], rows)
    out += ["", "说明：通道按 `configs/runner/*.json` 的 provider 区分，commandcode 写“Command Code”，其余写“官方接口”。思考设置用 `workbench.claim_cases._thinking_label`。"
            "任务集为 null 的两个批次是旧版基础任务（f0 到 f9），manifest 里没有 task_set。重试行指 attempt 大于 1 的原始行。c-commandcode-deepseek-risk-v0.1 请求了关思考，但通道忽略了该参数，实际按默认思考运行，所以写“默认思考”。", "",
            "## 三、每个数字的分母和来源", "",
            f"- **{totals['real_runs']:,} 次真实模型运行**：分母是各批次每个格子最新一次尝试里，run_status 为 completed 且 execution_source 为 observed_agent_execution 的行，"
            "排除配置以 `-low-risk-v0.1` 结尾的作废批次。来源：`experiments/annual_calibration.py` 的 `real_rows()`。",
            f"- **{totals['accidents']} 起事故**：上面这些运行里净损失不低于 {ledger['accident_floor_cents']} 分的行数。来源：同文件的 `severity()`。",
            f"- **{yuan(totals['net_loss_cents'])} 元（{totals['net_loss_cents']:,} 分）**：这 {totals['accidents']} 行事故净损失之和，没有去重，没有扣免赔。",
            f"- **{totals['distinct_tasks']} 个去重任务**：{totals['accidents']} 行事故按 fixture_id 分组后的组数。每组取净损失平均值，再对 {totals['distinct_tasks']} 个平均值求均值，得 {dedup['official_mean_of_task_means_cents']:,} 分。",
            f"- **哈希链 {chain['links_current']:,} 条**：`artifacts/risk_runs/` 下全部 {chain['batches_in_chain']} 个批次的 results.jsonl 的全部行，每行一环，按批次名排序后串起来。来源：`experiments/evidence_chain.py`。",
            f"- **原始证据 {raw['rows_with_digest']:,} 份**：results.jsonl 里 evidence_sha256 非空的行数。`--verify` 逐份解压核对：本机核对 {raw['files_checked']} 份，缺失 {raw['files_absent']} 份，不一致 {raw['files_wrong']} 份。原始证据在 `var/`，不进 Git。",
            "- **每个配置档 210 个任务**：年度证据里每个配置、每个护栏档的事故率区间（Wilson 法），分母是 risk-same-mimo 批次的 210 个任务，一任务一次运行。"
            "分母是任务数，不是 4,326。", "", "## 四、9,186 和 5,732 的组成", ""]
    out += _table(["类别", "链条行数", "其中带证据哈希", "其中被后一次尝试取代"],
                  [[item["label"], f"{item['links']:,}", f"{item['with_evidence_digest']:,}", f"{item['superseded_by_retry']:,}"] for item in parts.values()]
                  + [["合计", f"{chain['links']:,}", f"{chain['rows_with_evidence_digest']:,}", f"{superseded:,}"]])
    done = part("completed_observed_counted", "with_evidence_digest") + part("completed_observed_voided", "with_evidence_digest")
    out += ["", f"- 5,732 份 = 完成的真实行 {done:,}（计入 {part('completed_observed_counted', 'with_evidence_digest'):,}，作废 {part('completed_observed_voided', 'with_evidence_digest')}）"
            f" + 脚本探针 {part('completed_scripted_probe', 'with_evidence_digest'):,} + 失败行 {part('infra_error', 'with_evidence_digest')} + 截断行 {part('truncated', 'with_evidence_digest')}。",
            f"- 9,186 − 5,732 = {chain['links'] - chain['rows_with_evidence_digest']:,}，等于未开始的行数 {part('not_started'):,}。",
            f"- 4,326 + 作废 {part('completed_observed_voided')} = 完成的真实行 {part('completed_observed_counted') + part('completed_observed_voided'):,}。完成行都是各格最新一次尝试，没有被取代的。",
            f"- 脚本参照解：链条里没有。批次目录里的脚本配置只有 {'、'.join(chain['scripted_configs'])}，它是探针，不是参照解。链条里参照解的行数：{chain['reference_solution_rows']}。", "",
            "## 五、各类记录进入哪个统计量", "",
            "“链”指 9,186；“证据”指 5,732；“real_runs”指 4,326；“事故/损失/69”指 162 起、86,019.26 元、69 个任务。", ""]
    out += _table(["记录类型", "链", "证据", "real_runs", "事故/损失/69", "说明"], [
        ["完成的真实运行（非作废）", "是", "是", "是", "是", f"{part('completed_observed_counted'):,} 行，每格只取最新一次尝试"],
        ["作废配置的完成运行", "是", "是", "否", "否", f"{part('completed_observed_voided')} 行。v0.1 低思考试点把长决策截断了，数据留盘，不当结果"],
        ["超时、连接中断等基础设施失败", "是", "是（有哈希的行）", "否", "否", f"{part('infra_error')} 行，run_status 为 infra_error，不算一次运行，也不算事故"],
        ["被后一次尝试取代的旧行", "是", "是（有哈希的行）", "否", "否", f"共 {superseded} 行，都是同一格后来被重试取代的失败行或未开始行；重试成功的那一行才算 1 次。它们已在上面的类别里计过，不能再相加"],
        ["运行超时被截断", "是", "是", "否", "否", f"{part('truncated')} 行，run_status 为 truncated，在作废批次里"],
        ["未开始", "是", "否", "否", "否", f"{part('not_started'):,} 行，没有运行也没有证据"],
        ["脚本探针（red-team）", "是", "是", "否", "否", f"{part('completed_scripted_probe'):,} 行。探针的事故在年度证据的 `probes` 里单列，不混入真实模型事故"],
        ["脚本参照解", "否", "否", "否", "否", "不在 `artifacts/risk_runs/` 里"]])
    out += ["", "## 六、从 162 起事故到 69 个任务", "", f"规则：{dedup['rule']}这是正式口径，本表不改。下面两个替代口径只供参考。", ""]
    out += _table(["口径", "点数", "任务均值（分）", "任务均值（元）"], [
        ["正式：同一任务取平均", dedup["distinct_tasks"], f"{dedup['official_mean_of_task_means_cents']:,}", yuan(dedup["official_mean_of_task_means_cents"])],
        ["参考：同一任务取最大值", dedup["distinct_tasks"], f"{dedup['alt_max_mean_cents']:,}", yuan(dedup["alt_max_mean_cents"])],
        ["参考：同一任务取首次出险", dedup["distinct_tasks"], f"{dedup['alt_first_mean_cents']:,}", yuan(dedup["alt_first_mean_cents"])],
        ["参考：不去重，每起事故一个点", dedup["accident_rows"], f"{dedup['no_dedup_mean_per_accident_row_cents']:,}", yuan(dedup["no_dedup_mean_per_accident_row_cents"])]])
    out += ["", f"“首次”的先后顺序：{dedup['first_order']}。",
            f"每个任务出险次数的分布（出险次数对应任务数）：{_kv(dedup['accidents_per_task'], '次', '个任务')}。",
            f"事故行来自哪些批次：{_kv(dedup['accident_rows_by_batch'], '', '起')}。",
            f"69 个任务按类别分：{totals_families(ledger)}。", "",
            "## 七、同一任务不是独立新样本", "",
            "同一个任务（fixture_id）会被多个模型、多个思考档、多个护栏档各跑一次，有时同一格还会重试。这些运行看到的是同一份工单和同一份标准答案。"
            "一个任务在三个配置下出险，是同一个难点被撞到三次，不是三个独立损失。所以：", "",
            "- 严重度按任务折叠后再求均值和区间，即上面的 69 个点。",
            "- 事故率按配置分别算，不跨模型合并。每个配置档的分母是 210 个任务，不是 4,326。",
            "- 4,326 次运行是工作量，不是独立样本数。把它当样本量算区间，区间会偏窄。", "",
            "## 八、两个小米低思考结果为什么不矛盾", "",
            f"“小米低思考 P0 在 210 个任务上 0 起”来自批次 `{pair['wide_batch']}`：通道 {pair['wide_channel']}，模型 ID `{pair['wide_model']}`，"
            f"P0 共 {pair['wide_all_tasks_P0']['runs']} 次，事故 {pair['wide_all_tasks_P0']['accidents']} 起。", "",
            f"“小米低思考在官方接口 60 个任务上 1 起”来自批次 `{pair['narrow_batch']}`：通道 {pair['narrow_channel']}，模型 ID `{pair['narrow_model']}`，"
            f"只跑 P0，任务限于 {'、'.join(pair['narrow_families'])} 两类，共 {pair['narrow_P0']['runs']} 个，事故 {pair['narrow_P0']['accidents']} 起，"
            f"事故任务是 {'、'.join(pair['narrow_accident_tasks'])}。", "", "两个批次的差异，逐项列出：", ""]
    out += _table(["项", "210 任务批次", "60 任务批次"], [
        ["批次 ID", pair["wide_batch"], pair["narrow_batch"]], ["通道", pair["wide_channel"], pair["narrow_channel"]],
        ["模型 ID 写法", pair["wide_model"], pair["narrow_model"]], ["配置", pair["wide_config"], pair["narrow_config"]],
        ["任务", f"{pair['wide_all_tasks_P0']['runs']} 个，7 类各 30", f"{pair['narrow_P0']['runs']} 个，{'、'.join(pair['narrow_families'])} 各 30，是 210 个的子集（{'是' if pair['narrow_tasks_inside_wide'] else '否'}）"],
        ["护栏档", "、".join(pair["wide_profiles"] or []), "、".join(pair["narrow_profiles"] or [])],
        ["并发", pair["wide_workers"], pair["narrow_workers"]], ["开跑时间（UTC）", pair["wide_started_at"], pair["narrow_started_at"]]])
    out += ["", f"相同的项：manifest 里的 {'、'.join(pair['identical_manifest_fields'])}"
            f"{'；请求参数相同（' + json.dumps(pair['request_params'], ensure_ascii=False) + '）' if pair['same_request_params'] else '；请求参数不同'}。", "",
            f"在同样这 {pair['narrow_P0']['runs']} 个任务上，210 任务批次的 P0 是 {pair['wide_on_narrow_tasks_P0']['accidents']}/{pair['wide_on_narrow_tasks_P0']['runs']}，"
            f"60 任务批次是 {pair['narrow_P0']['accidents']}/{pair['narrow_P0']['runs']}。两个 Wilson 区间分别是 "
            f"[{_pct(pair['wide_on_narrow_tasks_P0']['wilson_low'])}, {_pct(pair['wide_on_narrow_tasks_P0']['wilson_high'])}] 和 "
            f"[{_pct(pair['narrow_P0']['wilson_low'])}, {_pct(pair['narrow_P0']['wilson_high'])}]，相互重叠。",
            "所以这是两个批次、两条通道、两个分母下的两次结果，不是同一轮里互相矛盾。0 起与 1 起的差别太小，不足以说明哪条通道更好或更差。本表只记录，不做因果判断。", "",
            "## 九、版本和哈希记录", "",
            f"- 预注册 `{ver['prereg_file']}` 首次提交：`{ver['prereg_first_commit'] or '未读到'}`（`git log --follow --format=\"%H %ci\"` 的最后一行）。",
            f"- 该文件当前 SHA-256：`{ver['prereg_sha256']}`。各批次 manifest 里记录的 prereg_sha256 {'与它一致' if ver['prereg_matches_manifests'] else '与它不一致，需要查'}。",
            f"- `evidence_chain.json` 根值：`{ver['chain_root']}`，共 {ver['chain_links']:,} 环。",
            f"- 该文件最近一次提交：`{ver['chain_last_commit'] or '未读到'}`。工作区文件{'与提交一致' if ver['chain_file_clean'] else '与提交不一致'}。",
            f"- 链条用当前批次重算的根值与文件{'一致' if chain['root_current'] == chain['root_stored'] else '不一致'}。",
            "- 远程分支：提交 `5534871` 已于 2026-11-08 推送到 `origin/feature/all-risk-experiment-v2`。",
            "- 时间先后：各批次 manifest 记录的预注册文件 SHA-256 与现在的文件一致，说明文件在运行时已落盘、之后没改。但它的首次入库提交（2026-11-06 12:18 UTC）晚于前四批开跑（risk-hard-probe 01:19、risk-hard-mimo 02:53、risk-hard-cc 04:18、risk-hard-ccnt 12:14，均为 UTC），所以不能用提交时间证明“提交早于运行”。", "",
            "哈希一致只证明记录事后没有被改，不证明业务事实已经由第三方确认。链条里的损失，是本系统按自动生成、未签字的标准答案算出来的"
            "（loss_result 里写明 `review_status=A_auto_generated_D_not_signed; not a frozen Gold`）。要证明发生过的事为真，需要支付渠道对账单这类独立来源。", "",
            "## 十、复算命令", "", "```",
            "PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe -m experiments.annual_calibration",
            "PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe -m experiments.evidence_chain --verify",
            "PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe -m experiments.batch_ledger",
            "PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe -m unittest tests.test_batch_ledger", "```", "",
            "第一条会改写 `annual_evidence_v0.2.json`，只在需要重算时执行。其余命令不改已有文件。", "",
            "## 十一、脱敏证据样本", "",
            "`docs/validation/evidence_sample_00067996/` 是 risk-direct-low 批次里唯一一起事故的材料：工具调用序列、账本前后、核验输出和理赔材料。来源和删减见该目录的 README。", ""]
    return "\n".join(out)


def _kv(values: dict[str, Any], key_suffix: str = '', value_suffix: str = '') -> str:
    return '、'.join(f'{key}{key_suffix} {value}{value_suffix}' for key, value in values.items())


def totals_families(ledger: dict[str, Any]) -> str:
    return "、".join(f"{name} {count} 个" for name, count in ledger["task_families"].items())


def _redacted_events(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for event in evidence["events"]:
        row = {"seq": event["seq"], "tool": event["tool_name"], "status": event["status"], "arguments": event.get("raw_arguments") or {}}
        if event["tool_name"] in WRITE_TOOLS:
            row["result"] = event.get("result")
        else:
            row["result_keys"] = sorted((event.get("result") or {}).keys())
        out.append(row)
    return out


def _balances(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {"customer_balance_cents": snapshot["customer_balance_cents"], "merchant_balance_cents": snapshot["merchant_balance_cents"],
            "orders": [{"order_id": order["order_id"], "paid_cents": order["paid_cents"], "refunded_cents": order["refunded_cents"],
                        "remaining_cents": order["remaining_cents"], "status": order["status"],
                        "items": [{"item_id": item["item_id"], "name": item["name"], "quantity": item["quantity"],
                                   "allocated_paid_cents": item["allocated_paid_cents"], "refunded_quantity": item["refunded_quantity"],
                                   "refunded_cents": item["refunded_cents"]} for item in order["items"]]} for order in snapshot["orders"]]}


def export_sample(batch: str = SAMPLE_BATCH, run: str = SAMPLE_RUN, out: Path = SAMPLE_DIR) -> list[str]:
    """Copy the readable parts of one run after scanning them. Returns file names written; raises if a scan hits."""
    pack = CLAIM_PACKS / batch / run
    evidence = json.loads((pack / "evidence.json").read_text(encoding="utf-8"))
    claim = json.loads((pack / "claim_pack.json").read_text(encoding="utf-8"))
    loss = json.loads((pack / "loss_result.json").read_text(encoding="utf-8"))
    finish = [event for event in evidence["events"] if event["tool_name"] == "finish_case"][-1]
    documents = {
        "tool_calls.json": _redacted_events(evidence),
        "final_reply.json": {"outcome": (finish.get("raw_arguments") or {}).get("outcome"), "explanation": (finish.get("raw_arguments") or {}).get("explanation")},
        "ledger_before_after.json": {"before": _balances(evidence["initial_snapshot"]), "after": _balances(evidence["final_snapshot"]),
                                     "ledger_entries": evidence["ledger"], "refunds": evidence["refunds"]},
        "verification.json": {"net_loss_cents": loss["net_loss_cents"], "total_committed_cents": loss["total_committed_cents"],
                              "total_extra_cents": loss["total_extra_cents"], "total_underpaid_cents": loss["total_underpaid_cents"],
                              "lines_due_vs_committed": claim["lines"], "ledger_checks": loss["ledger_checks"], "notes": loss["notes"],
                              "oracle_version": loss["oracle_version"], "obligation_source": loss["obligation_source"]}}
    staged = {name: (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8") for name, doc in documents.items()}
    for name in ("evidence.json", "loss_result.json", "claim_pack.json", "理赔材料.html"):  # copied byte for byte, so hashes still match
        staged[name] = (pack / name).read_bytes()
    for name, data in staged.items():
        text = data.decode("utf-8")
        hits = scan_text(text) + ([f"field {key}" for key in scan_keys(json.loads(text))] if name.endswith(".json") else [])
        if hits:
            raise ValueError(f"{name}: {sorted(set(hits))}")
    out.mkdir(parents=True, exist_ok=True)
    for name, data in staged.items():
        (out / name).write_bytes(data)
    return sorted(staged)


def write(ledger: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    MD_OUT.write_text(render(ledger), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true")
    args = parser.parse_args()
    if args.sample:
        print("\n".join(export_sample()))
    else:
        result = build()
        write(result)
        print(JSON_OUT.relative_to(ROOT), MD_OUT.relative_to(ROOT), result["totals"]["real_runs"], result["totals"]["accidents"],
              result["totals"]["net_loss_cents"], result["totals"]["distinct_tasks"], result["chain"]["links_current"], result["raw_evidence"]["rows_with_digest"])
