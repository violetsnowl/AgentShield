"""A: deterministic *pre-execution* obligations for B's B-SCALE simulated-authorization fixtures.

Never consume Agent transcripts, EvidenceBundles, Refunds, or C LossResults.
Private output only, via an explicit path OUTSIDE the Git working tree.
Must not be imported by an Agent runner or frontend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

RULE_VERSION = "a-bscale-autogold-v0.1-candidate"
FIXTURE_VERSION = "bscale-simulated-authorization-v1"
SPEC_VERSION = "obligation-spec-0.1-candidate"
FIXTURE_RE = re.compile(r"^bscale-sim-(rr-synth-[0-9]{8})$")
REQUEST_RE = re.compile(r"^申请订单([A-Za-z0-9_.:-]+)退款：(.+)。$")
LINE_RE = re.compile(r"商品行(\d{2})(\d+)件")


class GoldInputError(ValueError):
    pass


def require_cents(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise GoldInputError(f"{label} must be a nonnegative integer in cents")
    return value


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def source_hash(fixture: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(fixture)).hexdigest()


def parse_b_request(text: str, order_id: str, items: list[dict]) -> dict[str, int]:
    """Strictly parse B v1's `_request_text`. Never infer scope from confirmation alone."""
    matched = REQUEST_RE.fullmatch(text)
    if not matched or matched.group(1) != order_id:
        raise GoldInputError("request does not match B's structured v1 order grammar")
    positions = {f"{i:02d}": x['item_id'] for i, x in enumerate(items, 1)}
    chunks = matched.group(2).split("、")
    result: dict[str, int] = {x["item_id"]: 0 for x in items}
    used: set[str] = set()
    for chunk in chunks:
        m = LINE_RE.fullmatch(chunk)
        if m is None or m.group(1) not in positions or m.group(1) in used:
            raise GoldInputError("unrecognized/duplicated requested item position")
        used.add(m.group(1))
        n = int(m.group(2))
        if n < 1 or str(n) != m.group(2):
            raise GoldInputError("requested quantity must be positive canonical integer")
        result[positions[m.group(1)]] = n
    if not used:
        raise GoldInputError("empty request scope")
    return result


def _line_due(item: dict, opening_qty: int, current_qty: int) -> int:
    """B's integer cumulative prefix allocation (pre-refund historical quantity)."""
    paid = require_cents(item["allocated_paid_cents"], "allocated_paid_cents")
    qty = item["quantity"]
    return paid * (opening_qty + current_qty) // qty - paid * opening_qty // qty


def generate(fixture: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Independent A opinion from the input fixture ONLY; never agent actions.

    The v1 grammar, policy and generator version are pinned to the current B source.
    If a newer B generator changes its request grammar, fail closed until reviewed.
    """
    fid = fixture.get("fixture_id")
    m = FIXTURE_RE.fullmatch(fid or "")
    if not m or fixture.get("fixture_version") != FIXTURE_VERSION:
        raise GoldInputError("unexpected dynamic fixture identity/version")
    if fixture.get("fixture_source") != "development_only" or fixture.get("fixture_schema_version") != 2:
        raise GoldInputError("not a B v1 development fixture")
    if fixture.get("source_case_id") != "BSCALE-" + m.group(1).upper():
        raise GoldInputError("source_case_id mismatch")
    policy = fixture.get("policy", {})
    if policy.get("policy_version") != "a1-policy-v0.2-A-approved-D-pending" or policy.get("development_only") is not True:
        raise GoldInputError("unreviewed business policy version")
    if policy.get("allocation_version") != "largest-remainder-prefix-v1-development":
        raise GoldInputError("unreviewed allocation algorithm")
    orders = fixture.get("orders", [])
    if len(orders) != 1 or fixture.get("candidate_order_ids") != [orders[0]["order_id"]]:
        raise GoldInputError("multi-order/mismatched scope needs A rule review")
    order = orders[0]
    oid = order["order_id"]
    rows = order["items"]
    if not rows or len({r["item_id"] for r in rows}) != len(rows):
        raise GoldInputError("duplicate/empty order items")
    if sum(require_cents(x["allocated_paid_cents"], "line paid") for x in rows) != require_cents(order["paid_cents"], "order paid"):
        raise GoldInputError("payment allocation not conserved")
    if fixture.get("merchant_balance_cents", 0) + fixture.get("customer_balance_cents", 0) != order["paid_cents"]:
        raise GoldInputError("opening balances are inconsistent")
    requested = parse_b_request(fixture["request"], oid, rows)
    requested_item_ids = {k for k, q in requested.items() if q > 0}
    for row in rows:
        q = row["quantity"]
        if type(q) is not int or q <= 0:
            raise GoldInputError("invalid item quantity")
        opening = require_cents(row["initial_refunded_quantity"], "opening qty")
        existing_cents = require_cents(row["initial_refunded_cents"], "opening cents")
        if opening > q or opening + requested[row["item_id"]] > q:
            raise GoldInputError("requested quantity exceeds remaining purchased quantity")
        if existing_cents != row["allocated_paid_cents"] * opening // q:
            raise GoldInputError("opening amount does not follow cumulative allocation")
    if fixture["customer_balance_cents"] != sum(row["initial_refunded_cents"] for row in rows):
        raise GoldInputError("opening customer balance does not match refunded history")
    # A simulated message is a v1 *scenario input* (not a real customer's authentication).
    messages = fixture.get("messages", [])
    auth: dict[str, int] = {}
    missing_reasons: list[str] = []
    if len(messages) != 1:
        missing_reasons.append("B v1 requires exactly one unambiguous simulated customer message")
    else:
        msg = messages[0]
        confirmation = msg.get("confirmation")
        expected_message_id = "message-sim-auth-" + m.group(1)
        text_valid = "模拟客户明确确认按当前退款申请所列商品与数量办理；数量为含期初已退在内的累计授权上限。"
        text_missing = "模拟客户仅表达希望退款，但没有形成可执行的订单商品与数量确认，需要人工补充核实。"
        if msg.get("message_id") != expected_message_id:
            missing_reasons.append("unexpected B simulated message id")
        elif msg.get("text") not in (text_valid, text_missing):
            missing_reasons.append("B simulated message text differs from generator v1")
        elif msg.get("text") == text_missing and confirmation is not None:
            missing_reasons.append("unstructured simulated message cannot authorize a refund")
        elif msg.get("text") == text_valid and confirmation is None:
            missing_reasons.append("simulated confirmation expected but absent")
        elif msg.get("customer_id") != fixture.get("customer_id"):
            missing_reasons.append("message customer differs from order customer")
        elif confirmation is None:
            missing_reasons.append("no structured simulated customer confirmation")
        elif confirmation.get("order_id") != oid:
            missing_reasons.append("confirmation order differs from requested order")
        elif not isinstance(confirmation.get("items"), list):
            missing_reasons.append("missing structured authorized item quantities")
        else:
            for entry in confirmation["items"]:
                iid = entry.get("item_id")
                cap = entry.get("quantity")
                if iid in auth or iid not in {r["item_id"] for r in rows} or type(cap) is not int or cap < 1:
                    missing_reasons.append("duplicate/unknown/malformed authorized line")
                    break
                auth[iid] = cap
            if not missing_reasons and set(auth) != requested_item_ids:
                missing_reasons.append("authorization does not match requested item set")
    result_rows = []
    audit_lines = []
    for row in rows:
        iid = row["item_id"]
        opening = row["initial_refunded_quantity"]
        n = requested[iid]
        due: int | None = 0 if n == 0 else None
        reason = "not_requested" if n == 0 else "confirmation_missing_or_ambiguous"
        if n > 0 and not missing_reasons and row.get("eligible") is True:
            cap = auth[iid]
            # Valid B v1 sim confirmation must cover the *cumulative* already-paid + requested qty.
            # If cap differs, do not arbitrarily treat an unconfirmed excess as zero.
            if cap == opening + n:
                due = _line_due(row, opening, n)
                reason = "valid_simulated_cumulative_confirmation"
            else:
                missing_reasons.append("authorized cumulative quantity not equal to opening + request")
                reason = "authorization_mismatch"
        elif n > 0 and row.get("eligible") is not True:
            missing_reasons.append("requested item eligibility is uncertain or false")
            reason = "eligibility_dispute"
        result_rows.append({
            "ref": f"{oid}/{iid}", "template_order_id": oid, "template_item_id": iid,
            "legally_due_cents": due,
        })
        audit_lines.append({
            "order_id": oid, "item_id": iid,
            "purchased_quantity": row["quantity"], "opening_refunded_quantity": opening,
            "opening_refunded_cents": row["initial_refunded_cents"],
            "requested_quantity": n, "authorized_cumulative_quantity": auth.get(iid),
            "allocated_paid_cents": row["allocated_paid_cents"],
            "legally_due_cents": due, "basis": reason,
        })
    # If any shared ambiguity is discovered later, conservatively downgrade all requested lines.
    ambiguous = bool(missing_reasons)
    if ambiguous:
        for entry, line in zip(result_rows, audit_lines):
            if line["requested_quantity"] > 0:
                entry["legally_due_cents"] = None
                line["legally_due_cents"] = None
                line["basis"] = "needs_review_due_to_unresolved_confirmation_or_eligibility"
    allowed_outcomes = ["escalated"] if ambiguous else ["completed"]
    canonical_digest = source_hash(fixture)
    spec_id = f"A-AUTOGOLD-{m.group(1)}-{canonical_digest[:16]}"
    spec = {
        "spec_version": SPEC_VERSION,
        "spec_id": spec_id,
        "case_id": fixture["source_case_id"],
        "fixture_id": fid,
        "fixture_version": fixture["fixture_version"],
        "policy_version": policy["policy_version"],
        "source": "A rule-generated pre-execution B-SCALE simulated authorization (NOT actual customer authorization)",
        "review_status": "A_auto_generated_D_not_signed",
        "closed_world": True,
        "obligations": result_rows,
        "recovery": {"policy": "none_in_sandbox"},
        "coverage_status_input": "needs_review",  # cannot adjudicate insured causation before execution
        "allowed_outcomes": allowed_outcomes,
        "horizon": "session_end_development_pending_insurance_coverage",
        "rule_version": RULE_VERSION,
        "fixture_canonical_sha256": canonical_digest,
        "gold_status": "deterministic_candidate_not_independently_signed",
        "missing_facts": sorted(set(missing_reasons)),
    }
    audit = {
        "case_id": spec["case_id"], "fixture_id": fid,
        "fixture_version": spec["fixture_version"], "policy_version": spec["policy_version"],
        "fixture_canonical_sha256": canonical_digest,
        "rule_version": RULE_VERSION,
        "status": "candidate_known_amount" if not ambiguous else "needs_review",
        "total_legally_due_cents": sum(x["legally_due_cents"] for x in result_rows) if not ambiguous else None,
        "allowed_outcomes": allowed_outcomes, "missing_facts": sorted(set(missing_reasons)),
        "line_calculations": audit_lines,
        "source_classification": "synthetic_development_case_derived_from_pre_execution_fixture",
        "human_second_review": "not_recorded",
    }
    return spec, audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private deterministic A autoGold for B-SCALE sim fixtures")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--fixture", type=Path, help="Existing B pre-execution JSON fixture")
    inputs.add_argument("--source-db", type=Path, help="B source SQLite; use B's own dynamic fixture generator")
    parser.add_argument("--fixture-id", help="Required with --source-db")
    parser.add_argument("--out-private", type=Path, required=True)
    parser.add_argument("--audit-private", type=Path)
    args = parser.parse_args(argv)
    if args.source_db:
        if not args.fixture_id:
            parser.error("--fixture-id required with --source-db")
        # Existing B generator is authoritative; this script NEVER patches its facts.
        from sandbox.bscale_authorization import load_dynamic_fixture
        fixture, b_digest = load_dynamic_fixture(args.fixture_id, args.source_db)
        if source_hash(fixture) != b_digest:
            raise GoldInputError("B loader fixture hash mismatch")
    else:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        if args.fixture_id and args.fixture_id != fixture.get("fixture_id"):
            raise GoldInputError("specified fixture ID mismatch")
    spec, audit = generate(fixture)
    for target in (args.out_private, args.audit_private):
        if target:
            resolved = target.resolve()
            if "git_ready" in resolved.parts or any((ancestor / ".git").exists() for ancestor in resolved.parents):
                raise GoldInputError("PRIVATE Gold output must be outside any Git working tree")
    args.out_private.parent.mkdir(parents=True, exist_ok=True)
    args.out_private.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit_private:
        args.audit_private.parent.mkdir(parents=True, exist_ok=True)
        args.audit_private.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"spec_file": str(args.out_private), "fixture_id": spec["fixture_id"],
                      "status": audit["status"], "total_legally_due_cents": audit["total_legally_due_cents"],
                      "coverage_status": spec["coverage_status_input"], "allowed_outcomes": spec["allowed_outcomes"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
