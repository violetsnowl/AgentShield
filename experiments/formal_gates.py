"""Gates for formal L1 runs. The committed plans fail these gates on purpose."""
from typing import Any

L1_REGULAR_TASKS = 24
L1_STRESS_TASKS = 4
L1_TASKS = L1_REGULAR_TASKS + L1_STRESS_TASKS
L1_REPEATS = 2
L1_AGENT_RUNS = L1_TASKS * L1_REPEATS
L1_BASELINE_RUNS = L1_TASKS
PRETRIAL_TARGET = 10

REQUIRED_GATES = {
    "tasks_frozen": "正式任务清单未冻结",
    "gold_frozen": "Gold 未冻结",
    "held_out_isolated": "A/D 私有留出答案仍不可接触",
    "budget_confirmed": "真实付费预算未确认",
    "decision_table_signed": "规则基线决策表尚未 A/D 双签",
}


def dev_launch_block(plan: dict[str, Any]) -> str | None:
    """Return a reason to refuse launching this plan through the development runner."""
    if plan.get("status") == "blocked":
        return "refusing plan: status is blocked; formal and paid pretrial runs are not authorized"
    if plan.get("counts_as_formal_run") is True:
        return "refusing plan: counts_as_formal_run must stay false until the formal manifest is frozen"
    if plan.get("launch_paid_api") is True:
        return "refusing plan: paid API launch is not authorized in this checkpoint"
    return None


def formal_blockers(plan: dict[str, Any], *, execute: bool, env_flag: str | None) -> list[str]:
    blockers = []
    if plan.get("status") != "ready":
        blockers.append("plan status is not ready")
    gates = plan.get("gates") or {}
    for key, label in REQUIRED_GATES.items():
        if gates.get(key) is not True:
            blockers.append(label)
    if plan.get("execute_authorized") is not True:
        blockers.append("execute_authorized is not true")
    if plan.get("agent_run_slots") != L1_AGENT_RUNS or plan.get("baseline_run_slots") != L1_BASELINE_RUNS:
        blockers.append(f"L1 shape must be {L1_AGENT_RUNS} agent runs and {L1_BASELINE_RUNS} baseline runs")
    if plan.get("independent_business_samples") != L1_TASKS:
        blockers.append("repeats are paired observations, not extra business samples")
    if plan.get("runs"):
        blockers.append("fixture list must stay empty until A/D freeze a public task manifest")
    blob = str(plan)
    for banned in ("datasets/gold", "holdout", "private_gold"):
        if banned in blob:
            blockers.append("plan references a private answer path: " + banned)
    if not execute:
        blockers.append("execute flag is off")
    if env_flag != "true":
        blockers.append("C_FORMAL_RUN_AUTHORIZED is not true")
    return blockers
