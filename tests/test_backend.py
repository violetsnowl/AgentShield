from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from sandbox.fixture import allocate


class AllocationTests(unittest.TestCase):
    def test_fixed_remainder_and_tie_break(self):
        self.assertEqual(allocate(10, [{"item_id": "b", "gross_cents": 7}, {"item_id": "a", "gross_cents": 7}]), {"b": 5, "a": 5})
        self.assertEqual(allocate(5, [{"item_id": "b", "gross_cents": 7}, {"item_id": "a", "gross_cents": 7}]), {"b": 2, "a": 3})
        self.assertEqual(allocate(1500, [{"item_id": "a", "gross_cents": 1002}, {"item_id": "b", "gross_cents": 501}]), {"a": 1000, "b": 500})


class BackendTests(unittest.TestCase):
    def setUp(self):
        Path("var").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir="var")
        self.db = str(Path(self.temp.name) / "test.sqlite3")
        self.admin_token = secrets.token_urlsafe(32)
        self.admin = {"Authorization": f"Bearer {self.admin_token}"}
        self.app = create_app(self.db, self.admin_token)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.session = self.new_session("tenant-a")
        self.sid = self.session["session"]["session_id"]
        self.headers = {"Authorization": f"Bearer {self.session['session_token']}"}
        self.case = self.call("get_case", {}).json()
        self.order = self.call("get_order", {"order_id": self.case["candidate_order_ids"][0]}).json()
        self.body = {"order_id": self.order["order_id"], "items": [{"item_id": self.order["items"][0]["item_id"], "quantity": 1}],
                     "confirmation_message_id": self.case["messages"][0]["message_id"], "expected_version": 1, "reason": "Development refund"}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def new_session(self, tenant):
        response = self.client.post("/api/v1/sessions", headers=self.admin, json={"tenant_id": tenant})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def call(self, name, body, key=None, headers=None, sid=None, client=None):
        transport = dict(headers or self.headers)
        transport["X-Call-ID"] = "call-test"
        if key is not None:
            transport["Idempotency-Key"] = key
        return (client or self.client).post(f"/api/v1/sessions/{sid or self.sid}/tools/{name}", headers=transport, json=body)

    def evidence(self):
        response = self.client.get(f"/api/v1/admin/sessions/{self.sid}/evidence", headers=self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def reject(self, response, code, status=409):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(set(response.json()), {"code", "message", "retryable", "request_id"})
        self.assertEqual(response.json()["code"], code)
        self.assertEqual(response.headers["X-Request-ID"], response.json()["request_id"])

    def test_whole_order_refund_and_conservation(self):
        body = {**self.body, "items": [{"item_id": item["item_id"], "quantity": item["quantity"]} for item in self.order["items"]]}
        response = self.call("submit_refund", body, "whole")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["amount_cents"], 1500)
        self.assertEqual([line["amount_cents"] for line in response.json()["items"]], [1000, 500])
        evidence = self.evidence()
        final = evidence["final_snapshot"]
        self.assertEqual((final["merchant_balance_cents"], final["customer_balance_cents"]), (200, 1500))
        self.assertEqual(final["orders"][0]["status"], "refunded")
        self.assertEqual(final["orders"][0]["remaining_cents"], 0)
        entry = evidence["ledger"][0]
        self.assertEqual(entry["merchant_delta_cents"] + entry["customer_delta_cents"], 0)
        self.assertEqual(entry["transaction_id"], response.json()["transaction_id"])

    def test_three_partial_refunds_tail_cents_fixed_values(self):
        amounts = []
        for version in (1, 2, 3):
            response = self.call("submit_refund", {**self.body, "expected_version": version}, f"partial-{version}")
            self.assertEqual(response.status_code, 200, response.text)
            amounts.append(response.json()["amount_cents"])
        self.assertEqual(amounts, [333, 333, 334])
        final = self.evidence()["final_snapshot"]
        self.assertEqual((final["merchant_balance_cents"], final["customer_balance_cents"]), (700, 1000))
        self.assertEqual(final["orders"][0]["items"][0]["refundable_quantity"], 0)
        self.assertEqual(final["orders"][0]["version"], 4)

    def test_same_key_replay_conflict_stale_and_new_key_limit(self):
        first = self.call("submit_refund", self.body, "same").json()
        retry = self.call("submit_refund", self.body, "same")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json(), first)
        self.reject(self.call("submit_refund", {**self.body, "reason": "different"}, "same"), "IDEMPOTENCY_CONFLICT")
        self.reject(self.call("submit_refund", self.body, "new"), "STALE_STATE")
        overflow = {**self.body, "expected_version": 2, "items": [{"item_id": self.body["items"][0]["item_id"], "quantity": 3}]}
        self.reject(self.call("submit_refund", overflow, "another"), "QUANTITY_LIMIT")
        evidence = self.evidence()
        self.assertEqual(len(evidence["refunds"]), 1)
        self.assertEqual(len(evidence["ledger"]), 1)
        self.assertEqual(sum(e["committed_amount_cents"] for e in evidence["events"]), 333)
        self.assertTrue(any(e["status"] == "replayed" for e in evidence["events"]))
        self.assertTrue(all(e["transaction_id"] is None and e["committed_amount_cents"] == 0 for e in evidence["events"] if e["status"] == "rejected"))

    def test_scope_matrix_session_tenant_order_item_message_admin(self):
        for tenant in ("tenant-a", "tenant-b"):
            other = self.new_session(tenant)
            other_sid = other["session"]["session_id"]
            other_headers = {"Authorization": f"Bearer {other['session_token']}"}
            other_case = self.call("get_case", {}, headers=other_headers, sid=other_sid).json()
            other_order = self.call("get_order", {"order_id": other_case["candidate_order_ids"][0]}, headers=other_headers, sid=other_sid).json()
            self.reject(self.call("get_case", {}, sid=other_sid), "FORBIDDEN", 403)
            self.reject(self.call("get_order", {"order_id": other_order["order_id"]}), "OBJECT_FORBIDDEN", 403)
            for changed in ({"order_id": other_order["order_id"]},
                            {"items": [{"item_id": other_order["items"][0]["item_id"], "quantity": 1}]},
                            {"confirmation_message_id": other_case["messages"][0]["message_id"]}):
                self.reject(self.call("submit_refund", {**self.body, **changed}, "scope"), "OBJECT_FORBIDDEN", 403)
        for resource in ("evidence", "events", "ledger"):
            self.reject(self.client.get(f"/api/v1/admin/sessions/{self.sid}/{resource}", headers=self.headers), "FORBIDDEN", 403)
        self.reject(self.client.post("/api/v1/sessions", headers=self.headers, json={"tenant_id": "hijack"}), "FORBIDDEN", 403)
        self.reject(self.call("get_case", {}, headers=self.admin), "UNAUTHORIZED", 401)
        self.assertEqual(self.evidence()["refunds"], [])

    def test_item_and_message_from_other_order_same_session_rejected(self):
        second = self.call("get_order", {"order_id": self.case["candidate_order_ids"][1]}).json()
        bad_item = {**self.body, "items": [{"item_id": second["items"][0]["item_id"], "quantity": 1}]}
        self.reject(self.call("submit_refund", bad_item, "bad-item"), "OBJECT_FORBIDDEN", 403)
        self.reject(self.call("submit_refund", {**self.body, "confirmation_message_id": self.case["messages"][2]["message_id"]}, "bad-message"), "CONFIRMATION_SCOPE")

    def test_structured_confirmation_cumulative_limit_and_eligibility(self):
        body = {**self.body, "confirmation_message_id": self.case["messages"][1]["message_id"]}
        self.assertEqual(self.call("submit_refund", body, "confirmed").status_code, 200)
        self.reject(self.call("submit_refund", {**body, "expected_version": 2}, "confirmed-new"), "CONFIRMATION_SCOPE")
        other_line = {**body, "expected_version": 2, "items": [{"item_id": self.order["items"][1]["item_id"], "quantity": 1}]}
        self.reject(self.call("submit_refund", other_line, "outside"), "CONFIRMATION_SCOPE")
        second = self.call("get_order", {"order_id": self.case["candidate_order_ids"][1]}).json()
        ineligible = {**self.body, "order_id": second["order_id"], "items": [{"item_id": second["items"][0]["item_id"], "quantity": 1}], "confirmation_message_id": self.case["messages"][2]["message_id"]}
        self.reject(self.call("submit_refund", ineligible, "ineligible"), "NOT_ELIGIBLE")

    def test_invalid_quantities_amount_channel_and_extra_fields_audited(self):
        for quantity in (0, -2, 1.5, 1.0, "1", True):
            body = {**self.body, "items": [{"item_id": self.body["items"][0]["item_id"], "quantity": quantity}]}
            self.reject(self.call("submit_refund", body, "invalid"), "INVALID_REQUEST", 422)
        for extra in ({"amount_cents": 500}, {"channel": "other"}, {"tenant_id": "other"}, {"session_id": "other"}, {"password": "test-secret"}):
            self.reject(self.call("submit_refund", {**self.body, **extra}, "invalid"), "INVALID_REQUEST", 422)
        self.reject(self.call("submit_refund", self.body), "MISSING_IDEMPOTENCY_KEY", 422)
        self.reject(self.call("submit_refund", {**self.body, "items": self.body["items"] * 2}, "duplicate"), "DUPLICATE_ITEM")
        evidence = self.evidence()
        self.assertEqual(len([e for e in evidence["events"] if e["status"] == "rejected"]), 13)
        self.assertNotIn("test-secret", json.dumps(evidence))
        self.assertEqual(evidence["ledger"], [])

    def test_exception_after_refund_insert_rolls_everything_back(self):
        with patch.object(self.app.state.store, "_insert_ledger", side_effect=RuntimeError("internal SQL secret")):
            self.reject(self.call("submit_refund", self.body, "rollback"), "INTERNAL_ERROR", 500)
        evidence = self.evidence()
        self.assertEqual(evidence["initial_snapshot"], evidence["final_snapshot"])
        self.assertEqual(evidence["refunds"], [])
        self.assertEqual(evidence["ledger"], [])
        self.assertNotIn("internal SQL secret", json.dumps(evidence))
        self.assertEqual(evidence["events"][-1]["status"], "error")
        self.assertEqual(self.call("submit_refund", self.body, "rollback").status_code, 200)

    def test_event_insert_failure_rolls_back_transaction_and_request(self):
        original = self.app.state.store._event
        def fault(*args, **kwargs):
            if args[6] == "succeeded":
                raise RuntimeError("event fault")
            return original(*args, **kwargs)
        with patch.object(self.app.state.store, "_event", side_effect=fault):
            self.reject(self.call("submit_refund", self.body, "event-fault"), "INTERNAL_ERROR", 500)
        evidence = self.evidence()
        self.assertEqual(evidence["refunds"], [])
        self.assertEqual(evidence["ledger"], [])
        self.assertEqual(self.call("submit_refund", self.body, "event-fault").status_code, 200)

    def test_restart_preserves_transactions_and_original_result(self):
        original = self.call("submit_refund", self.body, "persist").json()
        self.client.close()
        self.app = create_app(self.db, self.admin_token)
        self.client = TestClient(self.app)
        retry = self.call("submit_refund", self.body, "persist")
        self.assertEqual(retry.json(), original)
        self.assertEqual(len(self.evidence()["ledger"]), 1)
        con = sqlite3.connect(self.db)
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 1)
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            con.close()

    def test_two_independent_connections_same_key_near_simultaneous(self):
        barrier = threading.Barrier(2)
        def send():
            with TestClient(create_app(self.db, self.admin_token)) as client:
                barrier.wait(timeout=5)
                result = self.call("submit_refund", self.body, "concurrent", client=client)
                return result.status_code, result.json()
        with ThreadPoolExecutor(max_workers=2) as executor:
            a, b = list(executor.map(lambda _: send(), range(2)))
        self.assertEqual(a[0], 200)
        self.assertEqual(a, b)
        self.assertEqual(len(self.evidence()["ledger"]), 1)

    def test_finish_preserves_ledger_blocks_new_writes_allows_recovery(self):
        original = self.call("submit_refund", self.body, "first").json()
        ledger = self.evidence()["ledger"]
        finish = {"outcome": "completed", "explanation": "Caller declaration only", "expected_version": 2}
        result = self.call("finish_case", finish, "finish")
        self.assertEqual(result.json()["version"], 3)
        self.assertEqual(result.json()["status"], "finished")
        self.assertEqual(self.call("finish_case", finish, "finish").json(), result.json())
        self.assertEqual(self.call("submit_refund", self.body, "first").json(), original)
        self.reject(self.call("submit_refund", {**self.body, "expected_version": 2}, "new"), "SESSION_FINISHED")
        self.reject(self.call("finish_case", {**finish, "expected_version": 3}, "new-finish"), "SESSION_FINISHED")
        self.assertEqual(self.evidence()["ledger"], ledger)
        history = self.call("get_refund_history", {"order_id": self.order["order_id"], "idempotency_key": "first"}).json()
        self.assertEqual(history["transaction_id"], original["transaction_id"])

    def test_submit_response_discarded_then_history_recovery(self):
        # Test-layer simulation: execute fully, discard the response before caller can inspect it.
        self.call("submit_refund", self.body, "lost-response")
        history = self.call("get_refund_history", {"order_id": self.order["order_id"], "idempotency_key": "lost-response"}).json()
        self.assertEqual(history["request_status"], "committed")
        self.assertEqual(len(history["refunds"]), 1)
        retry = self.call("submit_refund", self.body, "lost-response").json()
        self.assertEqual(retry["transaction_id"], history["transaction_id"])
        self.assertEqual(retry["amount_cents"], 333)
        self.assertEqual(len(self.evidence()["ledger"]), 1)

    def test_snapshot_isolation_events_pagination_and_no_tokens(self):
        self.call("submit_refund", self.body, "one")
        evidence = self.evidence()
        self.assertEqual(evidence["initial_snapshot"]["orders"][0]["version"], 1)
        other = self.new_session("tenant-a")
        other_state = self.client.get(f"/api/v1/sessions/{other['session']['session_id']}/status", headers={"Authorization": f"Bearer {other['session_token']}"}).json()
        self.assertEqual(other_state["version"], 1)
        page = self.client.get(f"/api/v1/admin/sessions/{self.sid}/events?after_seq=2", headers=self.admin).json()
        self.assertEqual([e["seq"] for e in page["events"]], [3])
        self.assertEqual(page["last_seq"], 3)
        self.assertTrue(all(e["client_receipt"] == "unknown" for e in evidence["events"]))
        self.assertNotIn(self.admin_token, json.dumps(evidence))
        self.assertNotIn(self.session["session_token"], json.dumps(evidence))

    def test_not_found_tools_no_fake_success(self):
        # Human review is implemented in bc-0.2; unknown tools must still never succeed.
        self.reject(self.call("unimplemented_tool", {}), "NOT_FOUND", 404)
        self.reject(self.client.get("/api/v1/quotes", headers=self.admin), "NOT_FOUND", 404)

    def test_credentials_do_not_enter_audit_facts(self):
        body = {**self.body, "reason": "Do not log " + self.session["session_token"] + " or " + self.admin_token}
        self.assertEqual(self.call("submit_refund", body, "redacted").status_code, 200)
        self.reject(self.call("submit_refund", self.body, self.session["session_token"]), "INVALID_REQUEST", 422)
        evidence = json.dumps(self.evidence())
        self.assertNotIn(self.session["session_token"], evidence)
        self.assertNotIn(self.admin_token, evidence)
        self.assertIn("[REDACTED]", evidence)

    def test_unexpected_read_error_has_safe_error_shape(self):
        with patch.object(self.app.state.store, "state", side_effect=RuntimeError("do not expose SQL")):
            response = self.client.get(f"/api/v1/sessions/{self.sid}/status", headers=self.headers)
            self.reject(response, "INTERNAL_ERROR", 500)
            self.assertNotIn("SQL", response.text)

    def test_idempotency_compares_original_parameters_before_redaction(self):
        first = {**self.body, "reason": "Bearer first-private-value"}
        second = {**self.body, "reason": "Bearer second-private-value"}
        self.assertEqual(self.call("submit_refund", first, "redaction-key").status_code, 200)
        self.reject(self.call("submit_refund", second, "redaction-key"), "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.call("submit_refund", first, "redaction-key").status_code, 200)
        evidence = json.dumps(self.evidence())
        self.assertNotIn("first-private-value", evidence)
        self.assertNotIn("second-private-value", evidence)


if __name__ == "__main__":
    Path("var").mkdir(exist_ok=True)
    unittest.main()
