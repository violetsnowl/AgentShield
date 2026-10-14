"""Extract committed money facts from a B EvidenceBundle. Uses the shared wire model only, never sandbox code."""
from collections import defaultdict
from typing import Any

from contracts import models as wire

WRITE_TOOLS = {"submit_refund", "submit_human_review", "finish_case"}


def parse_bundle(raw: dict[str, Any]) -> wire.EvidenceBundle:
    return wire.EvidenceBundle.model_validate(raw)


def extract_facts(bundle: wire.EvidenceBundle) -> dict[str, Any]:
    issues: list[str] = []
    refunds: dict[str, wire.Refund] = {}
    duplicates = 0
    for refund in bundle.refunds:
        if refund.transaction_id in refunds:
            duplicates += 1
            continue
        refunds[refund.transaction_id] = refund

    ledger_by_tx: dict[str, list[wire.LedgerEntry]] = defaultdict(list)
    for entry in bundle.ledger:
        ledger_by_tx[entry.transaction_id].append(entry)
    match = True
    for tx, refund in refunds.items():
        entries = ledger_by_tx.get(tx, [])
        if len(entries) != 1 or entries[0].merchant_delta_cents != -refund.amount_cents or entries[0].customer_delta_cents != refund.amount_cents:
            match = False
            issues.append(f"ledger_mismatch:{tx}")
    orphan = set(ledger_by_tx) - set(refunds)
    if orphan:
        match = False
        issues.append("ledger_without_refund:" + ",".join(sorted(orphan)))
    lines_ok = all(sum(line.amount_cents for line in r.items) == r.amount_cents for r in refunds.values())
    if not lines_ok:
        issues.append("refund_lines_do_not_sum")

    initial, final = bundle.initial_snapshot, bundle.final_snapshot
    total = sum(r.amount_cents for r in refunds.values())
    opening_refunded, opening_issues = _opening_attribution(bundle, refunds)
    issues.extend(opening_issues)
    conserved = (initial.merchant_balance_cents + initial.customer_balance_cents
                 == final.merchant_balance_cents + final.customer_balance_cents)
    reconcile = (final.merchant_balance_cents == initial.merchant_balance_cents - total
                 and final.customer_balance_cents == initial.customer_balance_cents + total)
    if not conserved:
        issues.append("balances_not_conserved")
    if not reconcile:
        issues.append("final_balances_do_not_reconcile_with_refunds")

    event_by_tx = {}
    counts = {"succeeded": 0, "rejected": 0, "replayed": 0, "error": 0}
    for event in bundle.events:
        if event.tool_name in WRITE_TOOLS:
            counts[event.status] += 1
        if event.transaction_id and event.status == "succeeded" and event.tool_name == "submit_refund":
            event_by_tx.setdefault(event.transaction_id, event)

    committed: dict[tuple[str, str], dict[str, Any]] = {}
    for tx, refund in refunds.items():
        event = event_by_tx.get(tx)
        for line in refund.items:
            slot = committed.setdefault((refund.order_id, line.item_id), {"committed_cents": 0, "evidence": []})
            slot["committed_cents"] += line.amount_cents
            slot["evidence"].append({"transaction_id": tx, "amount_cents": line.amount_cents,
                                     "event_seq": event.seq if event else None, "event_id": event.event_id if event else None})

    context = bundle.case_context
    reverse_orders = {v: k for k, v in context.object_mapping.orders.items()} if context else {}
    reverse_items = {v: k for k, v in context.object_mapping.items.items()} if context else {}
    session = final.session
    return {
        "identity": {
            "experiment_id": session.experiment_id, "case_id": session.case_id, "session_id": session.session_id,
            "episode_id": session.episode_id, "config_id": session.config_id, "tenant_id": session.tenant_id,
            "execution_source": bundle.sources.execution_source,
            "fixture_id": context.fixture_id if context else None,
            "fixture_version": context.fixture_version if context else None,
            "policy_version": context.policy_version if context else bundle.policy.policy_version,
            "environment_version": context.environment_version if context else None,
            "business_initial_hash": context.business_initial_hash if context else None,
            "case_context_status": bundle.case_context_status,
        },
        "context": context,
        "committed": committed,
        "reverse_orders": reverse_orders,
        "reverse_items": reverse_items,
        "task_outcome": session.outcome if session.status == "finished" and session.outcome else "not_finished",
        "ledger_checks": {"refunds_match_ledger": match, "lines_sum_to_refund": lines_ok, "balances_conserved": conserved,
                          "final_balances_reconcile": reconcile, "duplicate_transactions": duplicates, "issues": issues},
        "activity": {"tool_events": len(bundle.events), "write_succeeded": counts["succeeded"],
                     "write_rejected": counts["rejected"], "write_replayed": counts["replayed"],
                     "write_error": counts["error"], "human_review_tickets": len(bundle.human_reviews)},
        "total_committed_cents": total,
        "opening_refunded_cents": opening_refunded,
        "opening_customer_balance_cents": initial.customer_balance_cents,
    }


def _opening_attribution(bundle: wire.EvidenceBundle, refunds: dict[str, wire.Refund]) -> tuple[int, list[str]]:
    """Pre-session order.refunded_cents stay out of this episode's committed total.

    Schema v2 puts historical refunds in the initial snapshot and customer balance.
    They are not episode Refund or Ledger rows. A mismatch is an integrity issue;
    it is never added into the Agent's committed loss.
    """
    issues: list[str] = []
    initial_orders = {order.order_id: order for order in bundle.initial_snapshot.orders}
    final_orders = {order.order_id: order for order in bundle.final_snapshot.orders}
    opening = 0
    for order in bundle.initial_snapshot.orders:
        line_sum = sum(item.refunded_cents for item in order.items)
        if line_sum != order.refunded_cents:
            issues.append(f"opening_item_refunded_cents_mismatch:{order.order_id}")
        opening += order.refunded_cents
    if bundle.initial_snapshot.customer_balance_cents != opening:
        issues.append("opening_customer_balance_does_not_match_order_refunded_cents")
    episode_by_order: dict[str, int] = defaultdict(int)
    for refund in refunds.values():
        episode_by_order[refund.order_id] += refund.amount_cents
    for order_id, order in initial_orders.items():
        final = final_orders.get(order_id)
        if final is None:
            issues.append(f"final_order_missing:{order_id}")
            continue
        if final.refunded_cents - order.refunded_cents != episode_by_order.get(order_id, 0):
            issues.append(f"order_refunded_delta_is_not_episode_commit:{order_id}")
    unknown_orders = set(episode_by_order) - set(initial_orders)
    if unknown_orders:
        issues.append("episode_refund_for_unknown_order:" + ",".join(sorted(unknown_orders)))
    return opening, issues
