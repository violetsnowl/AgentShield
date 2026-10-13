"""Runner whitelist, local validation, recovery protocol and paid-run gate (no network, no model)."""
import json
from pathlib import Path
import tempfile
import unittest

from runners.attempts import AttemptLog
from runners.env import paid_authorization
from runners.loop import Budget, Executor, Pricing
from runners.sandbox_client import Transport
from runners.tools import LocalRejection, model_tool_specs, validate_call


class FakeSession:
    def __init__(self, script):
        self.script = list(script)
        self.sent = []

    def tool(self, name, arguments, *, idempotency_key, call_id):
        self.sent.append((name, arguments, idempotency_key, call_id))
        return self.script.pop(0)


class ToolSpecTests(unittest.TestCase):
    def test_seven_tools_inline_and_runner_owned_key_hidden(self):
        specs = model_tool_specs()
        self.assertEqual(len(specs), 7)
        text = json.dumps(specs)
        self.assertNotIn("$ref", text)
        history = next(s for s in specs if s["function"]["name"] == "get_refund_history")
        self.assertNotIn("idempotency_key", history["function"]["parameters"]["properties"])

    def test_validation_rejects_unknown_tool_bad_json_and_extra_fields(self):
        for name, text, code in (("delete_order", "{}", "UNKNOWN_TOOL"), ("get_order", "{not json", "INVALID_JSON_ARGUMENTS"),
                                 ("get_order", '{"order_id":"o","tenant_id":"x"}', "INVALID_ARGUMENTS"),
                                 ("get_refund_history", '{"order_id":"o","idempotency_key":"k"}', "INVALID_ARGUMENTS"),
                                 ("submit_refund", '{"order_id":"o","items":[{"item_id":"i","quantity":"2"}],"confirmation_message_id":"m","expected_version":1,"reason":"r"}', "INVALID_ARGUMENTS")):
            with self.subTest(name=name, code=code), self.assertRaises(LocalRejection) as raised:
                validate_call(name, text)
            self.assertEqual(raised.exception.code, code)
        self.assertEqual(validate_call("get_order", '{"order_id":"o-1"}'), {"order_id": "o-1"})


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.log = AttemptLog(Path(self.temp.name) / "attempts.jsonl")

    def tearDown(self):
        self.temp.cleanup()

    def test_lost_refund_response_probes_history_then_replays_same_key(self):
        ok = Transport("response", 200, {"transaction_id": "t1", "amount_cents": 333})
        session = FakeSession([Transport("timeout"), Transport("response", 200, {"request_status": "committed", "transaction_id": "t1"}), ok])
        args = {"order_id": "o", "items": [{"item_id": "i", "quantity": 1}], "confirmation_message_id": "m", "expected_version": 1, "reason": "r"}
        result, resolved = Executor(session, self.log, "run1", 2).execute("submit_refund", args, "model-1")
        self.assertTrue(resolved)
        self.assertEqual(result.payload["transaction_id"], "t1")
        (n1, a1, k1, _), (n2, a2, k2, _), (n3, a3, k3, _) = session.sent
        self.assertEqual((n1, n2, n3), ("submit_refund", "get_refund_history", "submit_refund"))
        self.assertIsNone(k2)
        self.assertEqual(a2["idempotency_key"], k1)
        self.assertEqual((k1, a1), (k3, a3))
        kinds = [row["kind"] for row in self.log.rows()]
        self.assertIn("recovery_decision", kinds)

    def test_unresolved_write_is_reported_not_retried_with_new_key(self):
        session = FakeSession([Transport("timeout")] * 2)
        result, resolved = Executor(session, self.log, "run2", 1).execute(
            "finish_case", {"outcome": "completed", "explanation": "x", "expected_version": 1}, "m")
        self.assertFalse(resolved)
        self.assertEqual(len({sent[2] for sent in session.sent}), 1)

    def test_4xx_is_a_resolved_rejection(self):
        session = FakeSession([Transport("response", 409, {"code": "STALE_STATE", "message": "x", "retryable": False, "request_id": "r"})])
        result, resolved = Executor(session, self.log, "run3", 2).execute(
            "finish_case", {"outcome": "completed", "explanation": "x", "expected_version": 9}, "m")
        self.assertTrue(resolved)
        self.assertEqual(len(session.sent), 1)


class BudgetAndPaidGateTests(unittest.TestCase):
    def test_paid_runs_default_off(self):
        self.assertFalse(paid_authorization({})[0])
        self.assertFalse(paid_authorization({"C_ENABLE_PAID_RUNS": "true", "C_MAX_COST_CNY": "0", "DEEPSEEK_API_KEY": "k"})[0])
        self.assertFalse(paid_authorization({"C_ENABLE_PAID_RUNS": "true", "C_MAX_COST_CNY": "5"})[0])
        self.assertTrue(paid_authorization({"C_ENABLE_PAID_RUNS": "true", "C_MAX_COST_CNY": "5", "DEEPSEEK_API_KEY": "k"})[0])

    def test_unknown_price_is_null_not_zero(self):
        self.assertIsNone(Pricing().cost(1000, 1000))
        self.assertAlmostEqual(Pricing(2.0, 8.0, "t").cost(1_000_000, 100_000), 2.8)
        with self.assertRaises(ValueError):
            Budget.from_mapping({"max_turns": 3, "surprise": 1})


if __name__ == "__main__":
    unittest.main()
