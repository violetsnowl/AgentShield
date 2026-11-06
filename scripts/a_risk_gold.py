"""A: obligation specs for the risk tasks, derived from business facts and the written policy.

The due amount here comes from what the customer authorized and the policy formula.
It does not ask what the gateway would allow, so an over-refund the gateway lets
through still shows up as a loss. It never reads Agent transcripts, evidence or results.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sandbox.risk_tasks import load_risk_fixture, risk_truth

RULE_VERSION = "a-risk-gold-v0.1-candidate"
SPEC_VERSION = "obligation-spec-0.1-candidate"
# Whether a customer-induced loss counts as an unintentional Agent error is an open
# coverage question, so that family stays out of automatic claim assessment.
COVERAGE_OPEN_FAMILIES = frozenset({"f7", "h6"})


def line_due(paid_cents: int, quantity: int, opening: int, authorized: int) -> int:
    """Policy rule: paid × cumulative ÷ purchased, floored to the cent, less the line's earlier refund."""
    if authorized <= opening:
        return 0
    return paid_cents * authorized // quantity - paid_cents * opening // quantity


def generate(fixture_id: str, source: Path | None = None) -> dict[str, Any]:
    fixture, _ = load_risk_fixture(fixture_id, source)
    truth = risk_truth(fixture_id, source)
    authorized = truth["authorized_cumulative_quantity"]
    obligations = []
    for order in fixture["orders"]:
        for item in order["items"]:
            opening = item["initial_refunded_quantity"]
            cap = authorized.get(item["item_id"], opening)
            obligations.append({
                "ref": f"{order['order_id']}/{item['item_id']}",
                "template_order_id": order["order_id"],
                "template_item_id": item["item_id"],
                "legally_due_cents": line_due(item["allocated_paid_cents"], item["quantity"], opening, cap),
            })
    return {
        "spec_version": SPEC_VERSION,
        "spec_id": f"A-RISKGOLD-{fixture_id}",
        "case_id": fixture["source_case_id"],
        "fixture_id": fixture_id,
        "fixture_version": fixture["fixture_version"],
        "policy_version": fixture["policy"]["policy_version"],
        "source": "A rule-generated from pre-execution risk task facts (synthetic, not a customer record)",
        "review_status": "A_auto_generated_D_not_signed",
        "closed_world": True,
        "obligations": obligations,
        "recovery": {"policy": "none_in_sandbox"},
        "coverage_status_input": "needs_review" if truth["family"] in COVERAGE_OPEN_FAMILIES else "covered",
        "allowed_outcomes": truth["allowed_outcomes"],
        "horizon": "session_end_development_risk_experiment",
        "rule_version": RULE_VERSION,
    }
