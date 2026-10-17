"""Registered public development fixtures, validation, canonical facts and per-run mapping."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from contracts.fixture_ids import (
    A_PUBLIC_FIXTURE_IDS,
    BASE_FIXTURE_IDS,
    BSCALE_SAMPLE_FIXTURE_IDS,
    GENERATED_FIXTURE_IDS,
)
from contracts.models import ALLOCATION_VERSION, VERSION, CaseContext, CanonicalBusinessSnapshot
from sandbox.bscale_authorization import is_dynamic_fixture_id, load_dynamic_fixture
from sandbox.fixture_models import DevelopmentFixture

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
GENERATED_ROOT = FIXTURE_ROOT / "generated"
GENERATED_REGISTRY = GENERATED_ROOT / "registry.json"
BSCALE_SAMPLE_REGISTRY = FIXTURE_ROOT / "bscale" / "registry.json"
A_PUBLIC_ROOT = Path(__file__).parents[1] / "docs" / "handoff" / "A1_public_candidates" / "development"
_BASE_REGISTRY = {
    "dev-refund-v1": ("dev-refund-v1.json", "dev-case-refund-v1", "dev-refund-v1-r1"),
    "dev-refund-v2": ("dev-refund-v2.json", "dev-case-refund-v2", "dev-refund-v2-r1"),
}
_A_PUBLIC_REGISTRY = {
    "a1-w_l-01": ("a1-w_l-01.json", "A1-W_L-01", "a1-w_l-01-r2",
                    "36e42a57df650fbf7edb087eb4e1c870b492a354f4d45551558b4c1cebf6c589"),
    "a1-p_h-03": ("a1-p_h-03.json", "A1-P_H-03", "a1-p_h-03-r2",
                    "42a19aea2e0200e8234ff33a0057336d35704a89c6dff662b98e41ce3966458e"),
    "a1-p_l-05": ("a1-p_l-05.json", "A1-P_L-05", "a1-p_l-05-r2",
                    "dcb31425fe8ae0b101d6c59fe88b1231ab2a7cc306387dd9d29b89521a28671d"),
    "eng-a0-06": ("eng-a0-06.json", "ENG-A0-06", "eng-a0-06-r2",
                   "45f1100e4307f56cce27b43fa5f44fafabd09134e442fa6f79328b33a3f5406d"),
}


class FixtureError(ValueError):
    pass


def _load_generated_registry():
    """Load only the checked-in generated manifest and require the exact source allowlist."""
    if not GENERATED_REGISTRY.exists():
        return {}
    try:
        raw = json.loads(GENERATED_REGISTRY.read_text(encoding="utf-8"))
        entries = raw["fixtures"]
        if raw.get("registration") != "source_controlled_development_only" or not isinstance(entries, list):
            raise FixtureError("Invalid generated fixture registry")
        result = {}
        for entry in entries:
            if set(entry) != {"fixture_id", "path", "source_case_id", "fixture_version", "fixture_content_sha256"}:
                raise FixtureError("Unexpected generated registry fields")
            fixture_id = entry["fixture_id"]
            if fixture_id in result:
                raise FixtureError("Duplicate generated fixture registration")
            result[fixture_id] = (
                entry["path"], entry["source_case_id"], entry["fixture_version"], entry["fixture_content_sha256"]
            )
        if tuple(result) != GENERATED_FIXTURE_IDS:
            raise FixtureError("Generated fixture registry differs from the source allowlist")
        return result
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, FixtureError):
            raise
        raise FixtureError("Generated fixture registry is invalid") from error


def _load_bscale_sample_registry():
    """Load the pinned B-SCALE draw without exposing a runtime registration path."""
    try:
        raw = json.loads(BSCALE_SAMPLE_REGISTRY.read_text(encoding="utf-8"))
        entries = raw["fixtures"]
        if raw.get("registration") != "source_controlled_development_only" or not isinstance(entries, list):
            raise FixtureError("Invalid B-SCALE sample registry")
        result = {}
        for entry in entries:
            if set(entry) != {"fixture_id", "path", "source_case_id", "fixture_version", "fixture_content_sha256"}:
                raise FixtureError("Unexpected B-SCALE sample registry fields")
            fixture_id = entry["fixture_id"]
            if fixture_id in result:
                raise FixtureError("Duplicate B-SCALE sample registration")
            result[fixture_id] = (
                entry["path"], entry["source_case_id"], entry["fixture_version"], entry["fixture_content_sha256"]
            )
        if tuple(result) != BSCALE_SAMPLE_FIXTURE_IDS:
            raise FixtureError("B-SCALE sample registry differs from the source allowlist")
        return result
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, FixtureError):
            raise
        raise FixtureError("B-SCALE sample registry is invalid") from error


if tuple(_BASE_REGISTRY) != BASE_FIXTURE_IDS:
    raise RuntimeError("Base fixture registration differs from source allowlist")
if tuple(_A_PUBLIC_REGISTRY) != A_PUBLIC_FIXTURE_IDS:
    raise RuntimeError("A public fixture registration differs from source allowlist")
REGISTRY = MappingProxyType(
    _BASE_REGISTRY | _load_generated_registry() | _load_bscale_sample_registry() | _A_PUBLIC_REGISTRY
)


def allocate(paid, lines):
    """Integer largest-remainder allocation, stable lexical TEMPLATE item-id tie break."""
    total = sum(line["gross_cents"] for line in lines)
    if not lines or total <= 0 or paid < 0 or paid > total:
        raise ValueError("Invalid development allocation inputs")
    result = {line["item_id"]: paid * line["gross_cents"] // total for line in lines}
    ranking = sorted(lines, key=lambda line: (-(paid * line["gross_cents"] % total), line["item_id"]))
    for line in ranking[:paid - sum(result.values())]:
        result[line["item_id"]] += 1
    return result


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def business_hash(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_fixture(data):
    """Validate all cross-object facts before a session or mapping can be inserted."""
    fixture = DevelopmentFixture.model_validate(data).model_dump(mode="json")
    if type(data["fixture_schema_version"]) is not int or type(data["customer_balance_cents"]) is not int:
        raise FixtureError("Integer fixture version and balances required")
    if data["policy"]["development_only"] is not True:
        raise FixtureError("Development-only policy required")
    if fixture["policy"]["allocation_version"] != ALLOCATION_VERSION:
        raise FixtureError("Unsupported allocation version")
    if fixture["parent_case_id"] == fixture["source_case_id"]:
        raise FixtureError("A case cannot be its own parent")
    ids = [fixture["customer_id"]]
    orders = {}
    opening_refund_total = 0
    for order in fixture["orders"]:
        ids.append(order["order_id"])
        ids.extend(line["item_id"] for line in order["items"])
        allocations = allocate(order["paid_cents"], order["items"])
        if any(line["allocated_paid_cents"] != allocations[line["item_id"]] for line in order["items"]):
            raise FixtureError("Declared allocation or tail cents do not match development rules")
        if sum(line["allocated_paid_cents"] for line in order["items"]) != order["paid_cents"]:
            raise FixtureError("Order allocation does not conserve money")
        for line in order["items"]:
            quantity = line["initial_refunded_quantity"]
            amount = line["initial_refunded_cents"]
            source = line["initial_refund_source"]
            if fixture["fixture_schema_version"] == 1 and (quantity != 0 or amount != 0 or source is not None):
                raise FixtureError("Fixture schema v1 cannot carry opening refund history")
            if quantity > line["quantity"]:
                raise FixtureError("Opening refunded quantity exceeds purchased quantity")
            expected = line["allocated_paid_cents"] * quantity // line["quantity"]
            if amount != expected:
                raise FixtureError("Opening refunded cents do not match cumulative allocation")
            if (quantity > 0) != (source == "pre_session_business_history"):
                raise FixtureError("Opening refund history requires its explicit pre-session source")
            if quantity > 0 and not line["eligible"]:
                raise FixtureError("Opening refund history cannot target an ineligible line")
            opening_refund_total += amount
        orders[order["order_id"]] = order
    ids.extend(message["message_id"] for message in fixture["messages"])
    if len(ids) != len(set(ids)):
        raise FixtureError("Template object IDs must be globally unique within a fixture")
    candidates = fixture["candidate_order_ids"]
    if len(candidates) != len(set(candidates)) or set(candidates) != set(orders):
        raise FixtureError("Candidate scope must list each authorized order exactly once")
    original_paid = sum(order["paid_cents"] for order in orders.values())
    if fixture["merchant_balance_cents"] != original_paid - opening_refund_total:
        raise FixtureError("Opening merchant balance must equal paid funds less pre-session refunds")
    if fixture["customer_balance_cents"] != opening_refund_total:
        raise FixtureError("Opening customer balance must equal pre-session refunds")
    if fixture["merchant_balance_cents"] + fixture["customer_balance_cents"] != original_paid:
        raise FixtureError("Opening balances do not conserve money")
    for message in fixture["messages"]:
        if message["customer_id"] != fixture["customer_id"] or not message["text"] or len(message["text"]) > 2000:
            raise FixtureError("Invalid public message customer or text")
        confirmation = message["confirmation"]
        if confirmation is None:
            continue
        if confirmation["order_id"] not in orders or not 1 <= len(confirmation["items"]) <= 30:
            raise FixtureError("Invalid confirmation order or items")
        allowed = {line["item_id"]: line for line in orders[confirmation["order_id"]]["items"]}
        refs = [line["item_id"] for line in confirmation["items"]]
        if len(refs) != len(set(refs)):
            raise FixtureError("Duplicate confirmation item")
        for line in confirmation["items"]:
            if line["item_id"] not in allowed or line["quantity"] > allowed[line["item_id"]]["quantity"]:
                raise FixtureError("Confirmation exceeds purchased object scope")
    if not fixture["policy"]["rules"] or any(not rule or len(rule) > 2000 for rule in fixture["policy"]["rules"]):
        raise FixtureError("Public policy rules required")
    return fixture


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FixtureError("Duplicate JSON property")
        result[key] = value
    return result


def _invalid_constant(_):
    raise FixtureError("Non-finite JSON number")


def load_fixture(fixture_id):
    if is_dynamic_fixture_id(fixture_id):
        try:
            data, content_hash = load_dynamic_fixture(fixture_id)
            fixture = validate_fixture(data)
            if fixture["fixture_id"] != fixture_id:
                raise FixtureError("Dynamic B-SCALE fixture identity differs from its request")
            return fixture, content_hash
        except (OSError, ValueError, KeyError, TypeError) as error:
            if isinstance(error, FixtureError):
                raise
            raise FixtureError("Dynamic B-SCALE fixture is invalid or unavailable") from error
    if fixture_id not in REGISTRY:
        raise FixtureError("Unregistered development fixture")
    registration = REGISTRY[fixture_id]
    filename, source_case_id, version = registration[:3]
    expected_hash = registration[3] if len(registration) == 4 else None
    try:
        root = (A_PUBLIC_ROOT if fixture_id in A_PUBLIC_FIXTURE_IDS else FIXTURE_ROOT).resolve()
        path = (root / filename).resolve(strict=True)
        if not path.is_relative_to(root) or path.suffix != ".json" or path.name == "registry.json":
            raise FixtureError("Fixture is outside the registered directory")
        if path.stat().st_size > 512_000:
            raise FixtureError("Fixture exceeds development size limit")
        content = path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        if expected_hash is not None and content_hash != expected_hash:
            raise FixtureError("Generated fixture content differs from source registration")
        data = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_keys, parse_constant=_invalid_constant)
        fixture = validate_fixture(data)
        if (fixture["fixture_id"], fixture["source_case_id"], fixture["fixture_version"]) != (fixture_id, source_case_id, version):
            raise FixtureError("Fixture identity differs from its registration")
        return fixture, content_hash
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, FixtureError):
            raise
        raise FixtureError("Registered development fixture is invalid or unavailable") from error


def canonical_snapshot(fixture):
    orders = []
    for raw in fixture["orders"]:
        lines = []
        for raw_line in raw["items"]:
            refunded_quantity = raw_line["initial_refunded_quantity"]
            refunded_cents = raw_line["initial_refunded_cents"]
            lines.append({
                "item_id": raw_line["item_id"], "name": raw_line["name"], "quantity": raw_line["quantity"],
                "gross_cents": raw_line["gross_cents"], "allocated_paid_cents": raw_line["allocated_paid_cents"],
                "eligible": raw_line["eligible"], "refunded_quantity": refunded_quantity,
                "refundable_quantity": raw_line["quantity"] - refunded_quantity if raw_line["eligible"] else 0,
                "refunded_cents": refunded_cents,
            })
        order_refunded = sum(line["refunded_cents"] for line in lines)
        remaining = raw["paid_cents"] - order_refunded
        status = "refunded" if all(line["refunded_quantity"] == line["quantity"] for line in lines) else (
            "partially_refunded" if order_refunded else "paid"
        )
        orders.append({"order_id": raw["order_id"], "tenant_id": "template-tenant", "customer_id": fixture["customer_id"],
                       "currency": "CNY", "original_channel": "simulated_original", "paid_cents": raw["paid_cents"],
                       "remaining_cents": remaining, "refunded_cents": order_refunded, "status": status,
                       "version": 2 if order_refunded else 1, "allocation_version": ALLOCATION_VERSION, "items": lines})
    return CanonicalBusinessSnapshot.model_validate({"business_time": fixture["business_time"],
        "case": {"customer_id": fixture["customer_id"], "request": fixture["request"],
                 "candidate_order_ids": fixture["candidate_order_ids"], "messages": fixture["messages"]},
        "orders": orders, "policy": fixture["policy"], "merchant_balance_cents": fixture["merchant_balance_cents"],
        "customer_balance_cents": fixture["customer_balance_cents"]}).model_dump()


def snapshot(sid, args):
    fixture, content_hash = load_fixture(args["fixture_id"])
    canonical = canonical_snapshot(fixture)
    mapping = {"customers": {fixture["customer_id"]: f"customer-{sid}"},
               "orders": {order["order_id"]: f"order-{sid}-{i}" for i, order in enumerate(canonical["orders"], 1)},
               "items": {line["item_id"]: f"item-{sid}-{i}" for i, line in enumerate(
                   [line for order in canonical["orders"] for line in order["items"]], 1)},
               "messages": {message["message_id"]: f"message-{sid}-{i}" for i, message in enumerate(canonical["case"]["messages"], 1)}}
    context = CaseContext.model_validate({"case_id": fixture["source_case_id"], "source_case_id": fixture["source_case_id"],
        "parent_case_id": fixture["parent_case_id"], "family_id": fixture["family_id"], "fixture_id": fixture["fixture_id"],
        "fixture_version": fixture["fixture_version"], "fixture_content_sha256": content_hash,
        "policy_version": fixture["policy"]["policy_version"], "object_mapping": mapping,
        "canonical_initial": canonical, "business_initial_hash": business_hash(canonical)}).model_dump()
    sources = {"fixture_source": "development_only", "execution_source": args["execution_source"],
               "recovery_source": "none", "contract_source": "candidate_pending_review", "calculation_version": ALLOCATION_VERSION}
    state = deepcopy(canonical)
    for key in ("canonical_version", "environment_version", "business_time"):
        state.pop(key)
    case = state["case"]
    case.update(case_id=fixture["source_case_id"], customer_id=mapping["customers"][case["customer_id"]], sources=sources)
    case["candidate_order_ids"] = [mapping["orders"][oid] for oid in case["candidate_order_ids"]]
    for message in case["messages"]:
        message["message_id"] = mapping["messages"][message["message_id"]]
        message["customer_id"] = mapping["customers"][message["customer_id"]]
        if message["confirmation"] is not None:
            confirmation = message["confirmation"]
            confirmation["order_id"] = mapping["orders"][confirmation["order_id"]]
            for line in confirmation["items"]:
                line["item_id"] = mapping["items"][line["item_id"]]
    for order in state["orders"]:
        order["order_id"] = mapping["orders"][order["order_id"]]
        order["tenant_id"] = args["tenant_id"]
        order["customer_id"] = mapping["customers"][order["customer_id"]]
        for line in order["items"]:
            line["item_id"] = mapping["items"][line["item_id"]]
    state["session"] = {"session_id": sid, "episode_id": f"episode-{sid}", "case_id": fixture["source_case_id"],
        "tenant_id": args["tenant_id"], "experiment_id": args["experiment_id"], "config_id": args["config_id"],
        "status": "active", "version": 1, "outcome": None, "explanation": None, "sources": sources, "contract_version": VERSION}
    return state, context
