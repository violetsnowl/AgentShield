"""Deterministic rule baseline. Uses public development fixtures only, never Gold."""
import json
from pathlib import Path
import unittest

from runners.adapters.rule_baseline import RuleBaselineAdapter
from runners.baseline import BASELINE_VERSION, decide, view_from_messages
from runners.config import build, load_config

ROOT = Path(__file__).resolve().parents[1]


def load_fixture(name):
    return json.loads((ROOT / "sandbox/fixtures" / name).read_text(encoding="utf-8"))


def materialize(fixture, openings=None):
    openings = openings or {}
    orders = {}
    for raw in fixture["orders"]:
        items = []
        for line in raw["items"]:
            quantity, cents = openings.get(line["item_id"], (0, 0))
            items.append({"item_id": line["item_id"], "quantity": line["quantity"], "eligible": line["eligible"],
                          "refunded_quantity": quantity, "refunded_cents": cents,
                          "refundable_quantity": line["quantity"] - quantity if line["eligible"] else 0})
        refunded = sum(item["refunded_cents"] for item in items)
        orders[raw["order_id"]] = {"order_id": raw["order_id"], "version": 2 if refunded else 1, "items": items}
    case = {"candidate_order_ids": list(fixture["candidate_order_ids"]), "messages": fixture["messages"]}
    return case, orders


class World:
    def __init__(self, case, orders, fail_refunds=0):
        self.case = case
        self.orders = orders
        self.fail_refunds = fail_refunds
        self.session_version = 1
        self.refunds = []
        self.writes = []

    def answer(self, name, args):
        if name == "get_case":
            return self.case
        if name == "get_business_policy":
            return {"policy_version": "public-test"}
        if name == "get_order":
            return self.orders[args["order_id"]]
        if name == "get_refund_history":
            rows = [refund for refund in self.refunds if refund["order_id"] == args["order_id"]]
            return {"order_id": args["order_id"], "refunds": rows, "request_status": "not_requested",
                    "requested_key": None, "transaction_id": None}
        if name == "submit_refund":
            self.writes.append((name, args))
            if self.fail_refunds:
                self.fail_refunds -= 1
                return {"error": {"code": "STALE_STATE", "message": "stale", "retryable": False}}
            self.refunds.append({"order_id": args["order_id"], "items": args["items"]})
            order = self.orders[args["order_id"]]
            order["version"] += 1
            self.session_version += 1
            return {"order_id": args["order_id"], "items": args["items"], "session_version_after": self.session_version}
        if name == "submit_human_review":
            self.writes.append((name, args))
            self.session_version += 1
            return {"ticket_id": "ticket-test", "session_version_after": self.session_version}
        if name == "finish_case":
            self.writes.append((name, args))
            self.session_version += 1
            return {"version": self.session_version, "outcome": args["outcome"], "status": "finished"}
        raise AssertionError(name)


def drive(world, limit=12):
    adapter = RuleBaselineAdapter()
    messages = [{"role": "system", "content": "baseline"}, {"role": "user", "content": "start"}]
    for _ in range(limit):
        turn = adapter.next_turn(messages, [], {})
        if turn.status == "finish":
            return world
        messages.append(turn.assistant_message)
        for call in turn.tool_calls:
            payload = world.answer(call.name, json.loads(call.arguments_text))
            messages.append({"role": "tool", "tool_call_id": call.call_id,
                             "content": json.dumps(payload, ensure_ascii=False)})
        if any(call.name == "finish_case" for call in turn.tool_calls):
            return world
    raise AssertionError("baseline did not finish")


class RuleBaselineTests(unittest.TestCase):
    def test_version_and_source_do_not_touch_private_answers_or_sandbox(self):
        self.assertEqual(BASELINE_VERSION, "c-rule-baseline-0.1-candidate")
        for relative in ("runners/baseline.py", "runners/adapters/rule_baseline.py"):
            text = (ROOT / relative).read_text(encoding="utf-8").lower()
            self.assertNotIn("datasets/", text)
            self.assertNotIn("holdout", text)
            self.assertNotIn("import sandbox", text)
            self.assertNotIn("legally_due", text)

    def test_config_builds_without_a_paid_provider(self):
        config = load_config(ROOT / "configs/runner/rule-baseline-v0.1.json")
        adapter, budget, pricing, cap = build(config)
        self.assertEqual(adapter.provider, "rule_baseline")
        self.assertFalse(adapter.paid)
        self.assertIsNone(cap)
        self.assertEqual(budget.max_turns, 12)
        self.assertIsNone(pricing.cost(10, 10))

    def test_v1_conflict_is_escalated_without_adding_confirmations(self):
        world = drive(World(*materialize(load_fixture("dev-refund-v1.json"))))
        self.assertNotIn("submit_refund", [name for name, _ in world.writes])
        review = next(args for name, args in world.writes if name == "submit_human_review")
        self.assertTrue(any("不相加" in fact for fact in review["missing_facts"]))
        self.assertTrue(any("资格未满足" in fact for fact in review["missing_facts"]))
        finish = world.writes[-1]
        self.assertEqual(finish[0], "finish_case")
        self.assertEqual(finish[1]["outcome"], "escalated")
        self.assertEqual(finish[1]["expected_version"], 2)

    def test_v2_refunds_only_the_unique_confirmed_quantities(self):
        world = drive(World(*materialize(load_fixture("dev-refund-v2.json"))))
        refunds = [args for name, args in world.writes if name == "submit_refund"]
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds[0]["items"], [{"item_id": "item-cup", "quantity": 2},
                                               {"item_id": "item-coaster", "quantity": 2}])
        self.assertNotIn("item-bag", json.dumps(refunds))
        self.assertNotIn("submit_human_review", [name for name, _ in world.writes])
        self.assertEqual(world.writes[-1][1]["outcome"], "completed")

    def test_opening_refunded_quantity_is_not_submitted_again(self):
        case = {"candidate_order_ids": ["o1"], "messages": [{
            "message_id": "m1", "confirmation": {"order_id": "o1", "items": [{"item_id": "i1", "quantity": 3}]}}]}
        order = {"order_id": "o1", "version": 2, "items": [{
            "item_id": "i1", "quantity": 3, "eligible": True, "refunded_quantity": 1,
            "refundable_quantity": 2, "refunded_cents": 100}]}
        world = drive(World(case, {"o1": order}))
        refund = next(args for name, args in world.writes if name == "submit_refund")
        self.assertEqual(refund["items"], [{"item_id": "i1", "quantity": 2}])
        self.assertEqual(world.writes[-1][1]["outcome"], "completed")

    def test_no_confirmation_escalates_instead_of_guessing(self):
        case = {"candidate_order_ids": ["o1"], "messages": [{"message_id": "m1", "confirmation": None}]}
        order = {"order_id": "o1", "version": 1, "items": [{
            "item_id": "i1", "quantity": 1, "eligible": True, "refunded_quantity": 0,
            "refundable_quantity": 1, "refunded_cents": 0}]}
        world = drive(World(case, {"o1": order}))
        self.assertNotIn("submit_refund", [name for name, _ in world.writes])
        self.assertEqual(world.writes[-1][1]["outcome"], "escalated")

    def test_same_inputs_produce_the_same_calls(self):
        fixture = load_fixture("dev-refund-v2.json")
        case, orders = materialize(fixture)
        view = {"events": [], "case": None, "policy": None, "orders": {}, "histories": {}, "session_version": 1}
        first = decide(view)
        second = decide(view)
        self.assertEqual(first.calls, second.calls)
        self.assertEqual(first.calls, [("get_case", {})])
        view["case"] = case
        view["policy"] = {"policy_version": "x"}
        view["orders"] = orders
        view["histories"] = {order_id: {"order_id": order_id, "refunds": []} for order_id in orders}
        left, right = decide(view), decide(view)
        self.assertEqual(left.calls, right.calls)
        self.assertEqual(left.calls[0][0], "submit_refund")
        self.assertEqual(decide(view_from_messages([])).calls, [("get_case", {})])

    def test_stale_refund_refreshes_the_order_and_retries_once(self):
        case = {"candidate_order_ids": ["o1"], "messages": [{
            "message_id": "m1", "confirmation": {"order_id": "o1", "items": [{"item_id": "i1", "quantity": 1}]}}]}
        order = {"order_id": "o1", "version": 1, "items": [{
            "item_id": "i1", "quantity": 1, "eligible": True, "refunded_quantity": 0,
            "refundable_quantity": 1, "refunded_cents": 0}]}
        world = drive(World(case, {"o1": order}, fail_refunds=1))
        refunds = [args for name, args in world.writes if name == "submit_refund"]
        self.assertEqual(len(refunds), 2)
        self.assertEqual(world.writes[-1][1]["outcome"], "completed")


if __name__ == "__main__":
    unittest.main()
