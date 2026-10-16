"""Fixed-case real-agent development preparation. Does not launch paid calls.

The four public cases are registered only on the unpushed integration tree.
This module checks that C's plan, prompt, budget gate and failure policy are ready
to move there. It does not add fixture ids or a new execution_source enum.
"""
import json
from pathlib import Path
from typing import Any

from contracts.models import FixtureId

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "experiments/plans/fixed_cases_agent_dev_blocked.json"
NOTES_PATH = ROOT / "experiments/fixtures/fixed_case_baseline_notes.json"
SLOTS_PATH = ROOT / "experiments/fixtures/fixed_case_obligation_slots.json"

FIXED_CASES = (
    {"fixture_id": "A1-W_L-01", "focus": "整单退款"},
    {"fixture_id": "A1-P_H-03", "focus": "部分退款与相似订单"},
    {"fixture_id": "A1-P_L-05", "focus": "重复确认"},
    {"fixture_id": "ENG-A0-06", "focus": "资格不足与人工升级"},
)
P_H_03_MARK = "rule_baseline_conservative_escalation_possible_unnecessary_upgrade"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def local_allowlist_gap() -> list[str]:
    """Fixture ids present in the plan but absent from this checkout's wire enum."""
    allowed = set(FixtureId.__args__)
    return [case["fixture_id"] for case in FIXED_CASES if case["fixture_id"] not in allowed]


def readiness() -> dict[str, Any]:
    plan = _load(PLAN_PATH)
    notes = _load(NOTES_PATH)
    slots = _load(SLOTS_PATH)
    prompt = (ROOT / "runners/prompts/system_v0.1.md").read_text(encoding="utf-8")
    baseline = (ROOT / "runners/baseline.py").read_text(encoding="utf-8")
    blockers: list[str] = []
    if plan.get("status") != "blocked" or plan.get("launch_paid_api") is not False:
        blockers.append("固定案例真实 Agent 计划仍须保持阻断，付费授权未到")
    if plan.get("counts_as_formal_run") is not False:
        blockers.append("这四次是开发测试，不能计入正式 56 次")
    if plan.get("budget_confirmed") is not False or plan.get("paid_api_called") is not False:
        blockers.append("预算尚未确认，不能标记为已调用付费接口")
    ids = [run["fixture_id"] for run in plan["runs"]]
    if ids != [case["fixture_id"] for case in FIXED_CASES]:
        blockers.append("开发计划必须恰好是四个公开固定案例，各一次")
    if any(run.get("config") != "configs/runner/deepseek-fixed-dev-v0.1.json" for run in plan["runs"]):
        blockers.append("真实 Agent 开发测试使用独立的未冻结配置")
    mark = notes["A1-P_H-03"]
    if mark["classification"] != P_H_03_MARK or mark["business_judgment"] != "pending_A":
        blockers.append("A1-P_H-03 须保持为待 A 核对的保守转人工标记")
    if mark["hardcoded_refund"] is not False or "A1-P_H-03" in baseline or "order-main" in baseline:
        blockers.append("规则基线不得为 A1-P_H-03 硬编码退款")
    if "datasets/gold" in prompt or "legally_due" in prompt or "order-main" in prompt:
        blockers.append("提示词只能包含公开操作说明")
    if any(slot["legally_due_cents"] is not None or slot["review_status"] != "pending_A_D" for slot in slots["cases"]):
        blockers.append("义务金额须等 A/D 审核通过后再填写")
    missing = local_allowlist_gap()
    if missing:
        blockers.append("当前检出的 fixture 枚举还没有这四个固定案例：" + ", ".join(missing))
    return {
        "ready_to_launch": False,
        "paid_api_called": False,
        "counts_as_formal_run": False,
        "execution_source_wire": "scripted_test",
        "agent_execution_source_when_authorized": "observed_agent_execution",
        "blockers": blockers,
        "a1_p_h_03": mark,
    }
