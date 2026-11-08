"""What the workbench shows of the annual model. It only reads stored results and never recomputes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "configs/insurance/annual_results_v0.2.json"
CONTRACT = ROOT / "configs/insurance/research_contract_annual_v0.3.json"
ENHANCED_CONTRACT = ROOT / "configs/insurance/research_contract_annual_enhanced_v0.3.json"
ROWS = (("uninsured", "不投保"), ("Core", "按次免赔 ¥500、赔 80%"), ("Plus", "按次免赔 ¥200、赔 90%"), ("aggregate", "基础档"), ("enhanced", "增强档"))


def _yuan(value: float) -> int:
    return int(round(value))


def _row(label: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    return {"label": label, "premium_yuan": _yuan(raw.get("premium", 0.0)), "premium_capital_yuan": _yuan(raw.get("premium_with_capital", 0.0)), "mean_yuan": _yuan(raw["mean"]), "p99_yuan": _yuan(raw["p99"]), "cte99_yuan": _yuan(raw["cte99"])}


def _tier(raw: Mapping[str, Any], stronger: Mapping[str, Any]) -> dict[str, Any]:
    insured = raw["insured"]
    return {"tier": raw["tier"], "label": raw["label"], "monitored": raw["monitored"], "accidents": raw["accidents"], "runs": raw["runs"], "pricing_frequency": raw["frequency"],
            "expected_events": _yuan(raw["lambda"]), "uninsured_mean_yuan": _yuan(raw["uninsured"]["mean"]), "uninsured_cte99_yuan": _yuan(raw["uninsured"]["cte99"]),
            "premium_yuan": _yuan(insured["premium"]), "premium_capital_yuan": _yuan(insured["premium_with_capital"]), "insured_cte99_yuan": _yuan(insured["cte99"]), "claim_year_chance": insured["trigger_chance"], "insurable": raw["open"],
            "enhanced_offered": stronger["open"], "enhanced_premium_yuan": _yuan(stronger["insured"]["premium"]), "enhanced_premium_capital_yuan": _yuan(stronger["insured"]["premium_with_capital"]), "enhanced_cte99_yuan": _yuan(stronger["insured"]["cte99"])}


def _contract(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {key: raw[key] for key in ("contract_version", "product_tier", "annual_aggregate_deductible_cents", "coinsurance_bp", "annual_limit_cents")}


def load_annual_summary(results_path: Path = RESULTS, contract_path: Path = CONTRACT, enhanced_path: Path = ENHANCED_CONTRACT) -> dict[str, Any]:
    results = json.loads(results_path.read_text(encoding="utf-8"))
    return {"schema": "AgentShield.annual_summary.v0.1", "commercial_quote": False, "nature": "研究测算，频率来自合成任务的压力测试，难单占比、故障概率和时延是假设",
            "contracts": [_contract(contract_path), _contract(enhanced_path)],
            "premium_with_capital_yuan": [_yuan(results["structures"][key]["premium_with_capital"]) for key in ("aggregate", "enhanced")],
            "structures": [_row(label, results["structures"][key]) for key, label in ROWS], "tiers": [_tier(row, stronger) for row, stronger in zip(results["tiers"], results["enhanced"]["tiers"])],
            "latency": [{"hours": row["hours"], "loud_fault_loss_yuan": _yuan(row["loud_fault_loss"])} for row in results["latency"]],
            "premium_note": "保费按定价频率（95% 区间上界）计算；计入资本成本的数字是参考价，不计资本的数字是下限"}
