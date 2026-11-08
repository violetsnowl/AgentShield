"""Turn the risk batches into the evidence file the annual model reads.

  python -m experiments.annual_calibration

Severity is counted per task: repeat runs of one task are averaged first, so they do not pose as
independent losses. Frequency stays per configuration and is never pooled across models.
"""
from __future__ import annotations

import json
from pathlib import Path
import random
import sqlite3
import statistics
from typing import Any

from experiments.claim_pack import RESULTS_ROOT, ROOT, is_accident, latest_rows, model_of
from experiments.risk_summary import ACCIDENT_FLOOR_CENTS, wilson
from experiments.run_matrix import resolve_source
from workbench.claim_cases import OBSERVED, VOIDED_CONFIG_SUFFIX, _thinking_label

OUTPUT = ROOT / "configs/insurance/annual_evidence_v0.2.json"
SCRIPTED = "scripted_test"
# The 210 tasks every model ran; other batches only cover part of the seven families.
PAIRED_BATCH = "risk-same-mimo-20261106-104537"
OFF_ARM = "risk-hard-mimo-20261105-203613"
LOW_ARMS = ("risk-same-mimo-20261106-104537", "risk-same-deepseek-20261106-101526",
            "risk-same-glm-20261106-102633", "risk-same-qwen-20261106-103525")
SENTINEL_ARMS = {"off": "risk-direct-off-20261106-221729", "low": "risk-direct-low-20261106-221729"}
BOOTSTRAP_DRAWS = 20000


def completed(batch: str, results_root: Path, source: str) -> list[dict[str, Any]]:
    return [row for row in latest_rows(batch, results_root) if row.get("run_status") == "completed" and row.get("execution_source") == source]


def batches(results_root: Path) -> list[str]:
    return sorted(path.name for path in results_root.iterdir() if (path / "results.jsonl").is_file())


def real_rows(results_root: Path) -> dict[str, list[dict[str, Any]]]:
    found = {}
    for batch in batches(results_root):
        rows = completed(batch, results_root, OBSERVED)
        if rows and not str(rows[0].get("config_id")).endswith(VOIDED_CONFIG_SUFFIX):
            found[batch] = rows
    return found


def severity(rows_by_batch: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    per_task: dict[str, list[int]] = {}
    for rows in rows_by_batch.values():
        for row in rows:
            if is_accident(row):
                per_task.setdefault(row["fixture_id"], []).append(row["net_loss_cents"])
    means = {task: round(sum(values) / len(values)) for task, values in per_task.items()}
    ordered = sorted(means.values())
    rng = random.Random(20261106)
    draws = sorted(statistics.mean(rng.choices(ordered, k=len(ordered))) for _ in range(BOOTSTRAP_DRAWS))
    families: dict[str, list[int]] = {}
    for task, cents in means.items():
        families.setdefault(task.split("-")[2], []).append(cents)
    return {"accidents": sum(len(values) for values in per_task.values()), "net_loss_cents": sum(sum(values) for values in per_task.values()),
            "distinct_tasks": len(ordered), "task_mean_cents": ordered, "mean_cents": round(statistics.mean(ordered)),
            "median_cents": round(statistics.median(ordered)), "max_cents": ordered[-1],
            "mean_bootstrap_95_cents": [round(draws[int(BOOTSTRAP_DRAWS * 0.025)]), round(draws[int(BOOTSTRAP_DRAWS * 0.975)])],
            "by_family": {name: {"tasks": len(values), "mean_cents": round(statistics.mean(values)), "max_cents": max(values)}
                          for name, values in sorted(families.items())}}


def arm(batch: str, rows: list[dict[str, Any]], profile: str, tasks: set[str] | None = None) -> dict[str, Any]:
    cell = [row for row in rows if row["control_profile"] == profile and (tasks is None or row["fixture_id"] in tasks)]
    hits = sum(1 for row in cell if is_accident(row))
    low, high = wilson(hits, len(cell))
    config = str(cell[0].get("config_id"))
    return {"batch": batch, "config_id": config, "model": model_of(config).split("/")[-1], "thinking": _thinking_label(config), "control_profile": profile,
            "runs": len(cell), "accidents": hits, "wilson_low": low, "wilson_high": high,
            "cost_per_run_cny": round(sum(row.get("cost_cny") or 0 for row in cell) / len(cell), 5)}


def worst(arms: list[dict[str, Any]]) -> dict[str, Any]:
    return max(arms, key=lambda row: (row["accidents"], row["wilson_high"]))


def tiers(rows_by_batch: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    paired = {row["fixture_id"] for row in rows_by_batch[PAIRED_BATCH]}
    low_gate = [arm(batch, rows_by_batch[batch], "P2", paired) for batch in LOW_ARMS]
    low_open = [arm(batch, rows_by_batch[batch], profile, paired) for batch in LOW_ARMS for profile in ("P0", "P1")]
    off_open = [arm(OFF_ARM, rows_by_batch[OFF_ARM], profile, paired) for profile in ("P0", "P1")]
    off_gate = arm(OFF_ARM, rows_by_batch[OFF_ARM], "P2", paired)
    return {"A": {"label": "低思考 + P2", "gate": True, "thinking_off": False, "open_reference": worst(low_open), "evidence": worst(low_gate)},
            "B": {"label": "低思考 + P0 或 P1", "gate": False, "thinking_off": False, "evidence": worst(low_open)},
            "C": {"label": "关思考 + P2", "gate": True, "thinking_off": True, "open_reference": worst(off_open), "evidence": off_gate},
            "D": {"label": "关思考 + P0 或 P1", "gate": False, "thinking_off": True, "evidence": worst(off_open)}}


def probes(results_root: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for batch in batches(results_root):
        for row in completed(batch, results_root, SCRIPTED):
            if "red-team" not in str(row.get("config_id")):
                continue
            cell = out.setdefault(row["control_profile"], {"tasks": 0, "accidents": 0, "net_loss_cents": 0})
            cell["tasks"] += 1
            cell["accidents"] += int(is_accident(row))
            cell["net_loss_cents"] += row.get("net_loss_cents") or 0
    for cell in out.values():
        cell["per_task_cents"] = round(cell["net_loss_cents"] / cell["tasks"])
    return out


def natural_flow(source: Path) -> dict[str, Any]:
    """What a fault costs per task on ordinary refund requests, not on tasks built to go wrong."""
    connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        rows = connection.execute("select r.requested_cents, o.paid_cents - o.opening_refunded_cents from refund_requests r "
                                  "join orders o on r.order_id = o.order_id where r.agent_handled = 1").fetchall()
    finally:
        connection.close()
    whole_order = [max(remaining - requested, 0) for requested, remaining in rows]
    return {"tasks": len(rows), "whole_order_share": round(sum(1 for value in whole_order if value > 0) / len(rows), 4),
            "whole_order_per_task_cents": round(statistics.mean(whole_order)), "duplicate_per_task_cents": round(statistics.mean(requested for requested, _ in rows))}


def sentinel_rates(rows_by_batch: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    return {name: arm(batch, rows_by_batch[batch], "P0") for name, batch in SENTINEL_ARMS.items()}


def build(results_root: Path = RESULTS_ROOT, source: str | None = None) -> dict[str, Any]:
    rows_by_batch = real_rows(results_root)
    return {"schema": "AgentShield.annual_evidence.v0.1", "commercial_quote": False,
            "nature": "有意加难的合成任务上的压力测试，不是自然事故率", "accident_floor_cents": ACCIDENT_FLOOR_CENTS,
            "real_runs": sum(len(rows) for rows in rows_by_batch.values()), "severity": severity(rows_by_batch),
            "tiers": tiers(rows_by_batch), "probes": probes(results_root), "natural_flow": natural_flow(resolve_source(source)), "sentinel": sentinel_rates(rows_by_batch)}


if __name__ == "__main__":
    evidence = build()
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT), evidence["real_runs"], evidence["severity"]["accidents"], evidence["severity"]["distinct_tasks"])
