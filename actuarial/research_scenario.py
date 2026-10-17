"""Shared study scenario for enterprise risk and Core/Plus reference premiums."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
from typing import Any, Mapping

from actuarial.claims import calculate_claim

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO = ROOT / "configs/insurance/research_scenario_v0.1.json"
DEFAULT_PRODUCTS = ROOT / "configs/insurance/research_products_P0_v0.1.json"
DEFAULT_DESIGN = ROOT / "configs/insurance/research_products_A4_candidate.json"
STRATA = ("whole_low", "whole_high", "partial_low", "partial_high")


def _decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _integer(value: Any, name: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f"{name} must be a valid integer")
    return value


def _cents(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain an object")
    return raw


def calculate_research_scenario(scenario: Mapping[str, Any], products: Mapping[str, Any],
                                designs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Calculate labeled assumption-only risk and premiums with A's claim formula."""
    if scenario.get("commercial_quote") is not False or scenario.get("currency") != "CNY":
        raise ValueError("research scenario must be noncommercial CNY")
    volume = _integer(scenario.get("annual_agent_task_volume"), "annual_agent_task_volume", positive=True)
    categories = scenario.get("categories")
    if not isinstance(categories, Mapping) or set(categories) != set(STRATA):
        raise ValueError("research scenario must contain the four registered categories")
    loading = _decimal(scenario.get("premium_loading_ratio"), "premium_loading_ratio")
    if loading < 0:
        raise ValueError("premium_loading_ratio must be nonnegative")

    category_rows: list[dict[str, Any]] = []
    total_tasks = 0
    expected_loss = Decimal(0)
    for key in STRATA:
        row = categories[key]
        if not isinstance(row, Mapping):
            raise ValueError(f"categories.{key} must be an object")
        count = _integer(row.get("task_count"), f"categories.{key}.task_count")
        probability = _decimal(row.get("accident_probability"), f"categories.{key}.accident_probability")
        loss_cents = _integer(row.get("average_accident_loss_cents"), f"categories.{key}.average_accident_loss_cents")
        if probability < 0 or probability > 1:
            raise ValueError("accident probability must be between zero and one")
        total_tasks += count
        weight = Decimal(count) / Decimal(volume)
        contribution = Decimal(volume) * weight * probability * Decimal(loss_cents)
        expected_loss += contribution
        category_rows.append({
            "key": key,
            "label": str(row.get("label") or key),
            "task_count": count,
            "weight": format(weight, "f"),
            "accident_probability": format(probability, "f"),
            "average_accident_loss_cents": loss_cents,
            "expected_annual_loss_cents": _cents(contribution),
        })
    if total_tasks != volume:
        raise ValueError("category task counts must equal annual_agent_task_volume")

    plans = products.get("plans")
    if not isinstance(plans, list) or {p.get("product_id") for p in plans if isinstance(p, Mapping)} != {
            "AgentShield-Core", "AgentShield-Plus"}:
        raise ValueError("exactly Core and Plus research plans are required")
    plan_rows: list[dict[str, Any]] = []
    design_rows = {row.get("product_id"): row for row in (designs or {}).get("plans", []) if isinstance(row, Mapping)}
    for plan in plans:
        if not isinstance(plan, Mapping) or plan.get("annual_aggregate_limit_status") != "display_only_not_enforced":
            raise ValueError("annual aggregate must remain display-only")
        expected_payout = Decimal(0)
        scenario_payouts: dict[str, int] = {}
        for category in category_rows:
            claim = calculate_claim({
                "event_id": f"research-{category['key']}",
                "net_loss_cents": category["average_accident_loss_cents"],
                "loss_status": "verified",
                "coverage_status": "covered",
            }, plan)
            payout = int(claim["payout_cents"])
            scenario_payouts[category["key"]] = payout
            expected_payout += (Decimal(volume) * Decimal(category["weight"])
                                * Decimal(category["accident_probability"]) * Decimal(payout))
        reference_premium = expected_payout * (Decimal(1) + loading)
        design = design_rows.get(plan["product_id"], {})
        plan_rows.append({
            "product_id": plan["product_id"],
            "display_name": plan["display_name"],
            "contract_version": plan["contract_version"],
            "deductible_cents": plan["deductible_cents"],
            "coinsurance_bp": plan["coinsurance_bp"],
            "occurrence_limit_cents": plan["occurrence_limit_cents"],
            "annual_aggregate_limit_cents": plan["annual_aggregate_limit_cents"],
            "annual_aggregate_limit_status": "display_only_not_enforced",
            "covered_loss": design.get("covered_event", plan["covered_loss"]),
            "exclusions": list(design.get("exclusions", plan["exclusions"])),
            "claims_basis": design.get("claims_basis", "Single-event net loss with one deductible and the stated participation rate"),
            "limit_design": design.get("limit_design", plan.get("basis", "Research limits")),
            "scenario_event_payout_cents": scenario_payouts,
            "annual_pure_risk_cost_cents": _cents(expected_payout),
            "annual_reference_premium_cents": _cents(reference_premium),
            "commercial_quote": False,
        })

    return {
        "schema": "AgentShield.research_risk_pricing_result.v0.1",
        "scenario_version": scenario.get("version"),
        "currency": "CNY",
        "annual_agent_task_volume": volume,
        "categories": category_rows,
        "premium_loading_ratio": format(loading, "f"),
        "expected_annual_economic_loss_cents": _cents(expected_loss),
        "risk_formula": "R = V × Σ(w_g × p_g × l_g)",
        "premium_formula": "P = (1 + loading) × V × Σ(w_g × p_g × I_g)",
        "claim_formula": "I = min(occurrence_limit, coinsurance × max(loss - deductible, 0))",
        "plans": plan_rows,
        "contract_context": dict(scenario.get("contract_context") or {}),
        "assumption_notice": scenario.get("assumption_notice"),
        "experience_pricing_status": "not_available_research_assumptions_only",
        "annual_aggregate_calculation_status": "display_only_not_enforced",
        "commercial_quote": False,
    }


def load_research_scenario(scenario_path: Path = DEFAULT_SCENARIO,
                           products_path: Path = DEFAULT_PRODUCTS,
                           design_path: Path = DEFAULT_DESIGN) -> dict[str, Any]:
    return calculate_research_scenario(_load_json(scenario_path), _load_json(products_path), _load_json(design_path))
