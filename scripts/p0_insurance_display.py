"""A/P0 study-only Core and Plus display results using unchanged A0 claim formula.

Does not approve C loss evidence, supply coverage approval or enforce annual caps.
Never writes to Git/agent folders; caller controls output path.

Example:
 python -m scripts.p0_insurance_display --output artifacts/insurance_p0/display.json
 python -m scripts.p0_insurance_display --loss-result /private/C/loss_result.json --output /private/claim_compare.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping
from actuarial.claims import calculate_claim

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACTS = ROOT / "configs/insurance/research_products_P0_v0.1.json"


def _load_contracts(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("commercial_quote") is not False or raw.get("annual_aggregate_enforced_in_A0") is not False:
        raise ValueError("Only noncommercial single-event P0 scenarios are supported")
    products = raw.get("plans")
    if not isinstance(products, list) or len(products) != 2:
        raise ValueError("Exactly two study plans required")
    if {p.get("product_id") for p in products} != {"AgentShield-Core", "AgentShield-Plus"}:
        raise ValueError("Unexpected P0 product set")
    for p in products:
        if p.get("annual_aggregate_limit_status") != "display_only_not_enforced":
            raise ValueError("Annual aggregate must explicitly be display only")
    return raw


def _claim_view(event: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    calc = calculate_claim(event, plan)
    return {
        "product_id": plan["product_id"],
        "contract_version": plan["contract_version"],
        "deductible_cents": plan["deductible_cents"],
        "coinsurance_bp": plan["coinsurance_bp"],
        "occurrence_limit_cents": plan["occurrence_limit_cents"],
        "annual_aggregate_limit_cents": plan["annual_aggregate_limit_cents"],
        "annual_aggregate_calculation_status": "display_only_not_enforced",
        **calc,
    }


def compare(event: Mapping[str, Any], contracts: Mapping[str, Any], *, source_type: str, label: str) -> dict[str, Any]:
    if source_type not in ("engineering_case", "observed_agent_execution_pending_review"):
        raise ValueError("A P0 display cannot certify real losses or review status")
    views = [_claim_view(event, p) for p in contracts["plans"]]
    return {
        "display_schema": "AgentShield.A_P0_claim_comparison.v0.1",
        "label": label,
        "source_type": source_type,
        "status": "engineering_illustration" if source_type == "engineering_case" else "observed_run_not_formally_admitted",
        "commercial_quote": False,
        "real_agent_insurance_claim": False,
        "event_id": event["event_id"],
        "net_loss_cents": event["net_loss_cents"],
        "loss_status": event["loss_status"],
        "coverage_status": event["coverage_status"],
        "claims": views,
        "notes": ["Both products use unchanged actuarial.claims.calculate_claim",
                  "An annual aggregate limit is displayed but is not applied in this event calculation",
                  "Zero verified event-level economic loss is not the same as fully completed business service"]
    }


def _engineering_samples() -> list[tuple[str, dict[str, Any]]]:
    return [
        ("normal_refund_no_extra_loss", {
            "event_id": "ENGINEERING-NORMAL-80-80", "net_loss_cents": 0,
            "loss_status": "verified", "coverage_status": "covered"}),
        ("overrefund_and_traceable_recovery", {
            "event_id": "ENGINEERING-80-800-RECOVER-200", "net_loss_cents": 52000,
            "loss_status": "verified", "coverage_status": "covered"}),
        ("observed_case_without_approved_coverage", {
            "event_id": "A1-W_L-01-REAL-EVIDENCE-NOT-SUPPLIED", "net_loss_cents": None,
            "loss_status": "needs_review", "coverage_status": "needs_review"}),
    ]


def sample_display(contracts: Mapping[str, Any]) -> dict[str, Any]:
    cases = []
    for label, event in _engineering_samples():
        # Third record is *only* a guarded placeholder, NOT actual evidence.
        source_type = "engineering_case" if label != "observed_case_without_approved_coverage" else "observed_agent_execution_pending_review"
        cases.append(compare(event, contracts, source_type=source_type, label=label))
    return {
        "schema": "AgentShield.A_P0_display_bundle.v0.1",
        "contracts_version": contracts["version"],
        "commercial_quote": False,
        "data_status": "engineering_samples_and_explicit_unknown_placeholder_only",
        "examples": cases,
        "premium": {"status": "insufficient_evidence", "annual_pure_risk_cost_cents": None,
                    "commercial_premium_cents": None, "reason": "No admissible representative stratum-level natural Agent loss estimates"}
    }


def _event_from_c_loss(obj: Mapping[str, Any]) -> dict[str, Any]:
    """Pass through C's *existing* statuses; never promote or silently fill missing values."""
    identity = obj.get("identity")
    if not isinstance(identity, Mapping):
        raise ValueError("LossResult.identity missing")
    event_id = identity.get("episode_id") or identity.get("case_id")
    if not event_id:
        raise ValueError("LossResult event identity missing")
    if obj.get("obligation_source") not in ("obligation_spec", "engineering_case"):
        # Without a matched Gold, force unknown instead of using C's observation as a loss.
        return {"event_id": event_id, "net_loss_cents": None,
                "loss_status": "needs_review", "coverage_status": "needs_review"}
    return {
        "event_id": event_id, "net_loss_cents": obj.get("net_loss_cents"),
        "loss_status": obj.get("loss_status"), "coverage_status": obj.get("coverage_status_input")
    }


def evaluate_saved_loss(loss_result: Mapping[str, Any], contracts: Mapping[str, Any]) -> dict[str, Any]:
    event = _event_from_c_loss(loss_result)
    # Critically: having A4 candidate Gold does NOT certify liability. The original
    # coverage_status_input=needs_review must survive for real runs.
    return compare(event, contracts, source_type="observed_agent_execution_pending_review", label="C_saved_loss_result_as_is")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A/P0 study display: no model/API calls, no annual-cap logic")
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACTS)
    parser.add_argument("--loss-result", type=Path, default=None, help="Optional saved C LossResult (not B gross refund)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    contracts = _load_contracts(args.contracts)
    if args.loss_result:
        raw = json.loads(args.loss_result.read_text(encoding="utf-8"))
        obj = evaluate_saved_loss(raw, contracts)
    else:
        obj = sample_display(contracts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"saved_to": str(args.output), "status": obj.get("status", obj.get("data_status")),
                      "commercial_quote": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
