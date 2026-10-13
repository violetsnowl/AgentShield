"""LossResult candidate wire model (C). Integer cents; null means unknown, never zero."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

LOSS_RESULT_VERSION = "loss-result-c-0.1-candidate"
Cents = Annotated[int, Field(strict=True, ge=0)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunIdentity(Strict):
    experiment_id: str | None
    case_id: str | None
    session_id: str | None
    episode_id: str | None
    config_id: str | None
    tenant_id: str | None
    execution_source: str | None
    fixture_id: str | None
    fixture_version: str | None
    policy_version: str | None
    environment_version: str | None
    business_initial_hash: str | None
    case_context_status: Literal["recorded", "legacy_unavailable", "not_applicable"]
    evidence_sha256: str | None


class EvidenceRef(Strict):
    transaction_id: str
    event_seq: int | None
    event_id: str | None
    amount_cents: Cents


class ObligationLoss(Strict):
    ref: str
    template_order_id: str | None
    template_item_id: str | None
    order_id: str | None
    item_id: str | None
    legally_due_cents: Cents | None
    committed_cents: Cents
    extra_cents: Cents | None
    underpaid_cents: Cents | None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class LedgerChecks(Strict):
    refunds_match_ledger: bool | None
    lines_sum_to_refund: bool | None
    balances_conserved: bool | None
    final_balances_reconcile: bool | None
    duplicate_transactions: int
    issues: list[str] = Field(default_factory=list)


class ActivityCounts(Strict):
    tool_events: int
    write_succeeded: int
    write_rejected: int
    write_replayed: int
    write_error: int
    human_review_tickets: int


class LossResult(Strict):
    loss_result_version: Literal["loss-result-c-0.1-candidate"] = LOSS_RESULT_VERSION
    oracle_version: str
    computed_at: str
    identity: RunIdentity
    obligation_source: Literal["obligation_spec", "engineering_case", "none"]
    obligation_spec_id: str | None
    horizon: str
    obligations: list[ObligationLoss]
    total_committed_cents: Cents
    total_extra_cents: Cents | None
    total_underpaid_cents: Cents | None
    traceable_recovery_cents: Cents | None
    net_loss_cents: Cents | None
    task_outcome: Literal["completed", "no_action", "escalated", "not_finished", "unknown"]
    policy_compliance: Literal["not_evaluated", "within_allowed_outcomes", "outside_allowed_outcomes"]
    loss_status: Literal["verified", "needs_review"]
    coverage_status_input: Literal["covered", "excluded", "needs_review"]
    ledger_checks: LedgerChecks | None
    activity: ActivityCounts | None
    unknown_parts: list[str]
    notes: list[str] = Field(default_factory=list)
    commercial_quote: Literal[False] = False
