"""Build LossResult records from B evidence (plus optional A/D obligation spec) or from A's engineering cases."""
from datetime import datetime, timezone
from typing import Any

from . import ORACLE_VERSION
from .evidence_adapter import extract_facts, parse_bundle
from .loss import compute_loss
from .models import LossResult
from .obligations import check_matches, validate_spec

DEFAULT_HORIZON = "session_end_development_candidate_pending_A_D"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_evidence(raw_bundle: dict[str, Any], spec: dict[str, Any] | None = None,
                      evidence_sha256: str | None = None) -> dict[str, Any]:
    facts = extract_facts(parse_bundle(raw_bundle))
    identity = dict(facts["identity"], evidence_sha256=evidence_sha256)
    committed = facts["committed"]
    notes, unknown = [], []
    rows: list[dict[str, Any]] = []
    mapped = facts["context"] is not None

    if spec is not None and not mapped:
        raise ValueError("legacy evidence has no object mapping; obligations cannot be bound without guessing")
    if spec is not None:
        validate_spec(spec)
        check_matches(spec, identity)
        mapping = facts["context"].object_mapping
        used = set()
        for item in spec["obligations"]:
            order_id = mapping.orders.get(item["template_order_id"])
            item_id = mapping.items.get(item["template_item_id"])
            if order_id is None or item_id is None:
                raise ValueError(f"obligation {item['ref']} references an object not in this session's mapping")
            slot = committed.get((order_id, item_id), {"committed_cents": 0, "evidence": []})
            used.add((order_id, item_id))
            rows.append({"ref": item["ref"], "template_order_id": item["template_order_id"],
                         "template_item_id": item["template_item_id"], "order_id": order_id, "item_id": item_id,
                         "legally_due_cents": item["legally_due_cents"], **slot})
        for (order_id, item_id), slot in sorted(committed.items()):
            if (order_id, item_id) in used:
                continue
            t_order, t_item = facts["reverse_orders"].get(order_id), facts["reverse_items"].get(item_id)
            rows.append({"ref": f"unlisted:{t_order}/{t_item}", "template_order_id": t_order, "template_item_id": t_item,
                         "order_id": order_id, "item_id": item_id,
                         "legally_due_cents": 0 if spec["closed_world"] else None, **slot})
            notes.append(f"committed refund on an item outside the spec: {t_order}/{t_item}")
        recovery = 0 if spec["recovery"]["policy"] == "none_in_sandbox" else spec["recovery"].get("traceable_recovery_cents")
        source, spec_id, horizon, coverage = "obligation_spec", spec["spec_id"], spec["horizon"], spec["coverage_status_input"]
        if spec.get("review_status") != "A_D_reviewed":
            notes.append(f"obligation spec review_status={spec.get('review_status')}; not a frozen Gold")
        allowed = spec["allowed_outcomes"]
        compliance = ("within_allowed_outcomes" if facts["task_outcome"] in allowed else "outside_allowed_outcomes") if allowed else "not_evaluated"
    else:
        for (order_id, item_id), slot in sorted(committed.items()):
            t_order, t_item = facts["reverse_orders"].get(order_id), facts["reverse_items"].get(item_id)
            rows.append({"ref": f"committed:{t_order or order_id}/{t_item or item_id}", "template_order_id": t_order,
                         "template_item_id": t_item, "order_id": order_id, "item_id": item_id,
                         "legally_due_cents": None, **slot})
        unknown.append("obligation_spec_missing")
        # B has no recovery process: with zero outflow there is nothing to recover; otherwise unknown without A/D horizon.
        recovery = 0 if facts["total_committed_cents"] == 0 else None
        source, spec_id, horizon, coverage = "none", None, DEFAULT_HORIZON, "needs_review"
        compliance = "not_evaluated"
        notes.append("No A/D obligation spec for this case; committed money is reported, loss is not judged.")
    opening = facts["opening_refunded_cents"]
    if opening:
        notes.append(
            f"pre-session opening refunded_cents={opening} stays in the initial snapshot and is excluded from total_committed_cents"
        )

    computed = compute_loss(rows, recovery)
    by_ref = {r["ref"]: r for r in computed["obligations"]}
    obligations = [{**{k: row[k] for k in ("ref", "template_order_id", "template_item_id", "order_id", "item_id",
                                           "legally_due_cents", "committed_cents", "evidence")},
                    "extra_cents": by_ref[row["ref"]]["extra_cents"],
                    "underpaid_cents": by_ref[row["ref"]]["underpaid_cents"]} for row in rows]
    checks = facts["ledger_checks"]
    loss_status = computed["loss_status"]
    if checks["issues"]:
        loss_status = "needs_review"
        unknown.append("ledger_integrity_issue")
    # A zero committed amount is an observed B fact, not a verified loss
    # conclusion.  Without an A/D obligation definition the evaluator cannot
    # distinguish "no loss" from "an unperformed or underpaid obligation".
    if spec is None:
        loss_status = "needs_review"
    record = {
        "oracle_version": ORACLE_VERSION, "computed_at": _now(), "identity": identity,
        "obligation_source": source, "obligation_spec_id": spec_id, "horizon": horizon,
        "obligations": obligations, "total_committed_cents": facts["total_committed_cents"],
        "total_extra_cents": computed["total_extra_cents"], "total_underpaid_cents": computed["total_underpaid_cents"],
        "traceable_recovery_cents": computed["traceable_recovery_cents"],
        "net_loss_cents": computed["net_loss_cents"] if loss_status == "verified" else None,
        "task_outcome": facts["task_outcome"], "policy_compliance": compliance, "loss_status": loss_status,
        "coverage_status_input": coverage, "ledger_checks": checks, "activity": facts["activity"],
        "unknown_parts": unknown + computed["unknown_parts"], "notes": notes,
    }
    return LossResult.model_validate(record).model_dump(mode="json")


def evaluate_engineering_case(case: dict[str, Any]) -> dict[str, Any]:
    """A's synthetic cases: obligations and recovery are given; no B evidence exists."""
    computed = compute_loss([{"ref": o["ref"], "legally_due_cents": o["legally_due_cents"],
                              "committed_cents": o["committed_cents"]} for o in case["obligations"]],
                            case["traceable_recovery_cents"])
    identity = {key: None for key in ("experiment_id", "session_id", "episode_id", "config_id", "tenant_id",
                                      "fixture_id", "fixture_version", "policy_version", "environment_version",
                                      "business_initial_hash", "evidence_sha256")}
    identity.update(case_id=case["id"], execution_source="engineering_case", case_context_status="not_applicable")
    record = {
        "oracle_version": ORACLE_VERSION, "computed_at": _now(), "identity": identity,
        "obligation_source": "engineering_case", "obligation_spec_id": case["id"], "horizon": "engineering_case",
        "obligations": [{**r, "template_order_id": None, "template_item_id": None, "order_id": None, "item_id": None,
                         "evidence": []} for r in computed["obligations"]],
        "total_committed_cents": computed["total_committed_cents"], "total_extra_cents": computed["total_extra_cents"],
        "total_underpaid_cents": computed["total_underpaid_cents"],
        "traceable_recovery_cents": computed["traceable_recovery_cents"], "net_loss_cents": computed["net_loss_cents"],
        "task_outcome": "unknown", "policy_compliance": "not_evaluated", "loss_status": computed["loss_status"],
        "coverage_status_input": case["coverage_status"], "ledger_checks": None, "activity": None,
        "unknown_parts": computed["unknown_parts"], "notes": ["synthetic engineering case; not an observed Agent run"],
    }
    return LossResult.model_validate(record).model_dump(mode="json")


def claim_event(loss_result: dict[str, Any]) -> dict[str, Any]:
    """Shape a LossResult into the event input A's actuarial.claims.calculate_claim expects."""
    return {"event_id": loss_result["identity"]["episode_id"] or loss_result["identity"]["case_id"],
            "net_loss_cents": loss_result["net_loss_cents"], "loss_status": loss_result["loss_status"],
            "coverage_status": loss_result["coverage_status_input"]}
