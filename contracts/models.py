"""Authoritative wire models. Schemas and tool specs are generated from these."""
from typing import Annotated, Any, Literal

from contracts.fixture_ids import FIXTURE_IDS

from pydantic import BaseModel, ConfigDict, Field

VERSION = "bc-0.3-candidate"
ALLOCATION_VERSION = "largest-remainder-prefix-v1-development"
ENVIRONMENT_VERSION = "sandbox-rules-v1-development"
Id = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Count = Annotated[int, Field(strict=True, ge=1)]
Cents = Annotated[int, Field(strict=True, ge=0)]
ExecutionSource = Literal["scripted_test", "mock_agent", "observed_agent_execution"]
BScaleDynamicFixtureId = Annotated[str, Field(pattern=r"^bscale-sim-rr-synth-[0-9]{8}$")]
FixtureId = Literal.__getitem__(FIXTURE_IDS) | BScaleDynamicFixtureId
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Error(Wire):
    code: str
    message: str
    retryable: bool
    request_id: str


class Sources(Wire):
    fixture_source: Literal["development_only"] = "development_only"
    execution_source: ExecutionSource = "scripted_test"
    recovery_source: Literal["none"] = "none"
    contract_source: Literal["candidate_pending_review"] = "candidate_pending_review"
    calculation_version: str = ALLOCATION_VERSION


class CreateSession(Wire):
    tenant_id: Id
    fixture_id: FixtureId = "dev-refund-v1"
    experiment_id: Id = "development"
    config_id: Id = "scripted-http-v1"
    execution_source: ExecutionSource = "scripted_test"


class SessionStatus(Wire):
    session_id: Id
    episode_id: Id
    case_id: Id
    tenant_id: Id
    experiment_id: Id
    config_id: Id
    status: Literal["active", "finished"]
    version: Count
    outcome: Literal["completed", "no_action", "escalated"] | None
    explanation: str | None
    sources: Sources
    contract_version: str = VERSION


class CreatedSession(Wire):
    session: SessionStatus
    session_token: str = Field(json_schema_extra={"writeOnly": True})
    case_context: "CaseContext | None" = None


class SessionPage(Wire):
    sessions: list[SessionStatus]
    next_offset: int | None


class FixtureMetadata(Wire):
    fixture_id: FixtureId
    fixture_version: Id
    source_case_id: Id
    policy_version: Id
    fixture_source: Literal["development_only"]
    review_status: Literal["pending_A_C_D_review"]


class FixtureCatalog(Wire):
    fixtures: list[FixtureMetadata]


class Empty(Wire):
    pass


class OrderRequest(Wire):
    order_id: Id


class RefundLine(Wire):
    item_id: Id
    quantity: Count


class RefundRequest(Wire):
    order_id: Id
    items: Annotated[list[RefundLine], Field(min_length=1, max_length=30)]
    confirmation_message_id: Id
    expected_version: Count
    reason: Text


class HistoryRequest(Wire):
    order_id: Id
    idempotency_key: Id | None = None


class FinishRequest(Wire):
    outcome: Literal["completed", "no_action", "escalated"]
    explanation: Text
    expected_version: Count


class HumanReviewRequest(Wire):
    category: Text
    missing_facts: Annotated[list[Text], Field(min_length=1, max_length=30)]
    evidence_message_ids: Annotated[list[Id], Field(max_length=30)]
    expected_version: Count


class HumanReviewTicket(Wire):
    ticket_id: Id
    session_id: Id
    case_id: Id
    category: Text
    missing_facts: list[Text]
    evidence_message_ids: list[Id]
    status: Literal["open"] = "open"
    created_at: str
    idempotency_key: Id
    call_id: Id
    session_version_before: Count
    session_version_after: Count
    sources: Sources


class Confirmation(Wire):
    order_id: Id
    items: list[RefundLine]


class Message(Wire):
    message_id: Id
    customer_id: Id
    text: str
    confirmation: Confirmation | None


class Case(Wire):
    case_id: Id
    customer_id: Id
    request: str
    candidate_order_ids: list[Id]
    messages: list[Message]
    evidence_status: Literal["development_public_facts"] = "development_public_facts"
    sources: Sources


class Item(Wire):
    item_id: Id
    name: str
    quantity: Count
    gross_cents: Cents
    allocated_paid_cents: Cents
    refunded_quantity: Cents
    refundable_quantity: Cents
    refunded_cents: Cents
    eligible: bool


class Order(Wire):
    order_id: Id
    tenant_id: Id
    customer_id: Id
    currency: Literal["CNY"] = "CNY"
    original_channel: Literal["simulated_original"] = "simulated_original"
    paid_cents: Cents
    refunded_cents: Cents
    remaining_cents: Cents
    status: Literal["paid", "partially_refunded", "refunded"]
    version: Count
    allocation_version: str = ALLOCATION_VERSION
    items: list[Item]


class Policy(Wire):
    policy_version: Id = "dev-policy-v1"
    development_only: Literal[True] = True
    rules: list[str]
    allocation_version: str = ALLOCATION_VERSION


class CommittedLine(RefundLine):
    amount_cents: Cents


class Refund(Wire):
    transaction_id: Id
    session_id: Id
    order_id: Id
    items: list[CommittedLine]
    amount_cents: Cents
    channel: Literal["simulated_original"] = "simulated_original"
    confirmation_message_id: Id
    idempotency_key: Id
    call_id: Id
    committed_at: str
    order_version_before: Count
    order_version_after: Count
    session_version_after: Count
    status: Literal["committed"] = "committed"


class History(Wire):
    order_id: Id
    refunds: list[Refund]
    requested_key: Id | None
    request_status: Literal["committed", "not_found", "not_requested"]
    transaction_id: Id | None


class LedgerEntry(Wire):
    entry_id: Id
    transaction_id: Id
    session_id: Id
    order_id: Id
    merchant_delta_cents: int
    customer_delta_cents: int
    merchant_balance_cents: Cents
    customer_balance_cents: Cents


class Snapshot(Wire):
    session: SessionStatus
    case: Case
    orders: list[Order]
    policy: Policy
    merchant_balance_cents: Cents
    customer_balance_cents: Cents


class CanonicalCase(Wire):
    customer_id: Id
    request: Text
    candidate_order_ids: list[Id]
    messages: list[Message]
    evidence_status: Literal["development_public_facts"] = "development_public_facts"


class CanonicalBusinessSnapshot(Wire):
    canonical_version: Literal["business-initial-v1"] = "business-initial-v1"
    environment_version: Literal["sandbox-rules-v1-development"] = ENVIRONMENT_VERSION
    business_time: str
    case: CanonicalCase
    orders: list[Order]
    policy: Policy
    merchant_balance_cents: Cents
    customer_balance_cents: Cents


class ObjectMapping(Wire):
    """Keys are stable template IDs; values are this session's IDs, never guessed from strings."""
    customers: dict[Id, Id]
    orders: dict[Id, Id]
    items: dict[Id, Id]
    messages: dict[Id, Id]


class CaseContext(Wire):
    case_id: Id
    source_case_id: Id
    parent_case_id: Id | None
    family_id: Id
    identity_semantics: Literal["development_case_candidate"] = "development_case_candidate"
    fixture_id: FixtureId
    fixture_version: Id
    fixture_content_sha256: Sha256
    fixture_source: Literal["development_only"] = "development_only"
    review_status: Literal["pending_A_C_D_review"] = "pending_A_C_D_review"
    policy_version: Id
    environment_version: Literal["sandbox-rules-v1-development"] = ENVIRONMENT_VERSION
    object_mapping: ObjectMapping
    canonical_initial: CanonicalBusinessSnapshot
    business_initial_hash: Sha256
    hash_algorithm: Literal["sha256-canonical-json-v1"] = "sha256-canonical-json-v1"


class ToolEvent(Wire):
    event_id: Id
    request_id: Id
    experiment_id: Id
    episode_id: Id
    case_id: Id
    session_id: Id
    config_id: Id
    seq: Count
    recorded_at: str
    business_time: str
    tool_name: str
    call_id: Id | None
    raw_arguments: dict[str, Any] | None
    validated_arguments: dict[str, Any] | None
    idempotency_key: Id | None
    status: Literal["succeeded", "rejected", "replayed", "error"]
    session_version_before: Count
    session_version_after: Count
    order_version_before: Count | None
    order_version_after: Count | None
    transaction_id: Id | None
    ticket_id: Id | None = None
    committed_amount_cents: Cents
    result: dict[str, Any] | None
    error: Error | None
    client_receipt: Literal["unknown"] = "unknown"
    sources: Sources


class EventPage(Wire):
    events: list[ToolEvent]
    last_seq: int


class Ledger(Wire):
    entries: list[LedgerEntry]


class EvidenceBundle(Wire):
    contract_version: str = VERSION
    schema_version: Literal[1, 2, 3] = 3
    exported_at: str
    initial_snapshot: Snapshot
    final_snapshot: Snapshot
    refunds: list[Refund]
    ledger: list[LedgerEntry]
    events: list[ToolEvent]
    human_reviews: list[HumanReviewTicket] = Field(default_factory=list)
    case_context_status: Literal["recorded", "legacy_unavailable"] = "legacy_unavailable"
    case_context: CaseContext | None = None
    policy: Policy
    sources: Sources
    receipt_semantics: Literal["server_commit_does_not_prove_client_receipt"] = "server_commit_does_not_prove_client_receipt"


# Registry drives HTTP routes, model tool definitions, schemas and examples checks.
TOOLS = {
    "get_case": (Empty, Case, False, "Read public case and messages."),
    "get_order": (OrderRequest, Order, False, "Read one authorized order."),
    "get_business_policy": (Empty, Policy, False, "Read fixed development business rules."),
    "get_refund_history": (HistoryRequest, History, False, "Read committed refunds and recover a request key."),
    "submit_refund": (RefundRequest, Refund, True, "Refund item quantities to the original simulated channel."),
    "submit_human_review": (HumanReviewRequest, HumanReviewTicket, True, "Create an open review ticket from public evidence; no adjudication or money movement."),
    "finish_case": (FinishRequest, SessionStatus, True, "Record a declared outcome without changing transactions."),
}
PLANNED_TOOLS = {}

CreatedSession.model_rebuild()
