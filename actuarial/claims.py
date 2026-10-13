"""Event-level research insurance indemnity from independent, verified net loss.

Deliberately does NOT consume B's gross refund records as economic losses.
"""
from typing import Any, Mapping
from .contracts import ContractError, ResearchContract, _int, _text

COVERAGE_STATUSES = frozenset({"covered", "excluded", "needs_review"})
LOSS_STATUSES = frozenset({"verified", "needs_review"})


def calculate_claim(event: Mapping[str, Any], contract: Mapping[str, Any] | ResearchContract) -> dict[str, Any]:
    """Apply event deductible once. Event is already grouped by independent C oracle.

    Expected event fields: event_id, net_loss_cents (int or None),
    loss_status, coverage_status. A/C must first validate the loss and coverage;
    this function cannot decide those business questions from refund totals.
    """
    c = contract if isinstance(contract, ResearchContract) else ResearchContract.from_mapping(contract)
    if not isinstance(event, Mapping):
        raise ContractError("event must be a mapping")
    for required in ("event_id", "net_loss_cents", "loss_status", "coverage_status"):
        if required not in event:
            raise ContractError(f"missing event field: {required}")
    event_id = _text(event["event_id"], "event_id")
    loss_status, coverage_status = event["loss_status"], event["coverage_status"]
    if loss_status not in LOSS_STATUSES or coverage_status not in COVERAGE_STATUSES:
        raise ContractError("unsupported loss_status/coverage_status")
    amount = event["net_loss_cents"]
    if amount is not None:
        _int(amount, "net_loss_cents")
    if loss_status == "verified" and amount is None:
        raise ContractError("verified loss must have known net_loss_cents; zero is an explicit 0")
    if loss_status == "needs_review" and amount is not None:
        raise ContractError("unverified loss must have net_loss_cents=null in A0")
    result = {
        "event_id": event_id,
        "contract_version": c.contract_version,
        "currency": c.currency,
        "net_loss_cents": amount,
        "loss_status": loss_status,
        "coverage_status": coverage_status,
        "claim_status": "needs_review",
        "payout_cents": None,
        "retained_loss_cents": None,
        "commercial_quote": False,
    }
    if loss_status != "verified" or coverage_status == "needs_review":
        return result
    if coverage_status == "excluded":
        result.update(claim_status="not_covered", payout_cents=0, retained_loss_cents=amount)
        return result
    eligible_cents = max(amount - c.deductible_cents, 0)
    # Nonnegative exact integer calculation; ROUND_HALF_UP at 1 cent.
    share_cents = (eligible_cents * c.coinsurance_bp + 5000) // 10000
    indemnity = min(c.occurrence_limit_cents, share_cents, amount)
    result.update(claim_status="assessed", payout_cents=indemnity, retained_loss_cents=amount - indemnity)
    return result
