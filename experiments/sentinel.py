"""Replay the sentinel check on recorded runs of the same tasks under two settings.

  python -m experiments.sentinel

The live monitor does not exist yet. This tests its decision rule on real outcomes: the same tasks, same model
and same route, once with low thinking (healthy) and once with thinking off (drifted). Sentinels are tasks the
configuration passed in its own test, so a healthy round only fails when a repeat run changes its answer. The
second signal is passive: the provider's own usage shows whether thinking happened, and it costs nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from math import comb
from pathlib import Path
from typing import Any

from experiments.check_reasoning import RAW_ROOT, reasoning_summary
from experiments.claim_pack import RESULTS_ROOT, ROOT, is_accident, latest_rows

OUTPUT = ROOT / "configs/insurance/sentinel_replay_v0.1.json"
PASSED_BASELINE = "risk-same-mimo-20261106-104537"
HEALTHY = "risk-direct-low-20261106-221729"
DRIFTED = "risk-direct-off-20261106-221729"


@dataclass(frozen=True)
class SentinelPlan:
    tasks_per_round: int = 10
    alarm_at: int = 3
    round_hours: float = 4.0

    def alarm(self, failures: int) -> bool:
        return failures >= self.alarm_at


def task_outcomes(batch: str, results_root: Path = RESULTS_ROOT, profile: str = "P0") -> dict[str, bool]:
    return {row["fixture_id"]: is_accident(row) for row in latest_rows(batch, results_root)
            if row["control_profile"] == profile and row.get("run_status") == "completed"}


def alarm_chance(outcomes: list[bool], plan: SentinelPlan) -> float:
    """Exact chance a round drawn without replacement from these recorded outcomes raises the alarm."""
    total, bad = len(outcomes), sum(outcomes)
    if plan.tasks_per_round > total:
        raise ValueError("a round cannot use more tasks than were recorded")
    ways = comb(total, plan.tasks_per_round)
    hits = sum(comb(bad, k) * comb(total - bad, plan.tasks_per_round - k) for k in range(plan.alarm_at, plan.tasks_per_round + 1))
    return hits / ways


def rounds_per_year(plan: SentinelPlan, hours: float = 8760.0) -> float:
    return hours / plan.round_hours


def replay(plan: SentinelPlan = SentinelPlan(), results_root: Path = RESULTS_ROOT, raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    baseline = task_outcomes(PASSED_BASELINE, results_root)
    healthy, drifted = task_outcomes(HEALTHY, results_root), task_outcomes(DRIFTED, results_root)
    sentinels = sorted(task for task in healthy if task in drifted and baseline.get(task) is False)
    healthy_outcomes = [healthy[task] for task in sentinels]
    drifted_outcomes = [drifted[task] for task in sentinels]
    healthy_alarm = alarm_chance(healthy_outcomes, plan)
    usage = {name: reasoning_summary(raw_root / batch) for name, batch in (("healthy", HEALTHY), ("drifted", DRIFTED))}
    return {"schema": "AgentShield.sentinel_replay.v0.1", "nature": "用已记录的真实运行回放判定规则，线上监测尚未实现",
            "plan": {"tasks_per_round": plan.tasks_per_round, "alarm_at": plan.alarm_at, "round_hours": plan.round_hours},
            "sentinel_tasks": len(sentinels), "healthy_failures": sum(healthy_outcomes), "drifted_failures": sum(drifted_outcomes),
            "healthy_alarm_chance": healthy_alarm, "healthy_alarms_per_year": healthy_alarm * rounds_per_year(plan),
            "drifted_alarm_chance": alarm_chance(drifted_outcomes, plan),
            "usage": {name: {key: row[key] for key in ("turns", "turns_with_reasoning")} for name, row in usage.items()}}


if __name__ == "__main__":
    result = replay()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
