"""Registered public development fixtures, validation, canonical facts and per-run mapping."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from contracts.models import ALLOCATION_VERSION, VERSION, CaseContext, CanonicalBusinessSnapshot
from sandbox.fixture_models import DevelopmentFixture

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
# Source-controlled allowlist; never accept an HTTP file path or a registration request.
REGISTRY = MappingProxyType({
    "dev-refund-v1": ("dev-refund-v1.json", "dev-case-refund-v1", "dev-refund-v1-r1"),
    "dev-refund-v2": ("dev-refund-v2.json", "dev-case-refund-v2", "dev-refund-v2-r1"),
})


class FixtureError(ValueError):
    pass


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
    for order in fixture["orders"]:
        ids.append(order["order_id"])
        ids.extend(line["item_id"] for line in order["items"])
        allocations = allocate(order["paid_cents"], order["items"])
        if any(line["allocated_paid_cents"] != allocations[line["item_id"]] for line in order["items"]):
            raise FixtureError("Declared allocation or tail cents do not match development rules")
        if sum(line["allocated_paid_cents"] for line in order["items"]) != order["paid_cents"]:
            raise FixtureError("Order allocation does not conserve money")
        orders[order["order_id"]] = order
    ids.extend(message["message_id"] for message in fixture["messages"])
    if len(ids) != len(set(ids)):
        raise FixtureError("Template object IDs must be globally unique within a fixture")
    candidates = fixture["candidate_order_ids"]
    if len(candidates) != len(set(candidates)) or set(candidates) != set(orders):
        raise FixtureError("Candidate scope must list each authorized order exactly once")
    if fixture["merchant_balance_cents"] != sum(order["paid_cents"] for order in orders.values()):
        raise FixtureError("Initial merchant balance must equal simulated paid funds")
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
    if fixture_id not in REGISTRY:
        raise FixtureError("Unregistered development fixture")
    filename, source_case_id, version = REGISTRY[fixture_id]
    try:
        path = (FIXTURE_ROOT / filename).resolve(strict=True)
        if path.parent != FIXTURE_ROOT.resolve() or path.suffix != ".json":
            raise FixtureError("Fixture is outside the registered directory")
        if path.stat().st_size > 512_000:
            raise FixtureError("Fixture exceeds development size limit")
        content = path.read_bytes()
        data = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_keys, parse_constant=_invalid_constant)
        fixture = validate_fixture(data)
        if (fixture["fixture_id"], fixture["source_case_id"], fixture["fixture_version"]) != (fixture_id, source_case_id, version):
            raise FixtureError("Fixture identity differs from its registration")
        return fixture, hashlib.sha256(content).hexdigest()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise FixtureError("Registered development fixture is invalid or unavailable") from error


def canonical_snapshot(fixture):
    orders = []
    for raw in fixture["orders"]:
        lines = [{**line, "refunded_quantity": 0, "refundable_quantity": line["quantity"] if line["eligible"] else 0,
                  "refunded_cents": 0} for line in raw["items"]]
        orders.append({"order_id": raw["order_id"], "tenant_id": "template-tenant", "customer_id": fixture["customer_id"],
                       "currency": "CNY", "original_channel": "simulated_original", "paid_cents": raw["paid_cents"],
                       "remaining_cents": raw["paid_cents"], "refunded_cents": 0, "status": "paid", "version": 1,
                       "allocation_version": ALLOCATION_VERSION, "items": lines})
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
