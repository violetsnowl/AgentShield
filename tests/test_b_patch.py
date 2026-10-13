"""01_B_PATCH regressions. Controlled source labels do not constitute model executions."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from tests import test_backend as baseline


class PatchTests(unittest.TestCase):
    setUp = baseline.BackendTests.setUp
    tearDown = baseline.BackendTests.tearDown
    new_session = baseline.BackendTests.new_session
    call = baseline.BackendTests.call
    evidence = baseline.BackendTests.evidence
    reject = baseline.BackendTests.reject

    def review_body(self):
        return {"category": "confirmation_needs_review", "missing_facts": ["Which public confirmation is current?"],
                "evidence_message_ids": [self.case["messages"][0]["message_id"]], "expected_version": 1}

    def test_invalid_business_parameters_keep_valid_correlation_and_key_is_reusable(self):
        invalid = {**self.body, "items": [{**self.body["items"][0], "quantity": 0}]}
        response = self.call("submit_refund", invalid, "invalid-then-fixed")
        self.reject(response, "INVALID_REQUEST", 422)
        evidence = self.evidence()
        event = evidence["events"][-1]
        self.assertEqual(event["call_id"], "call-test")
        self.assertEqual(event["idempotency_key"], "invalid-then-fixed")
        self.assertEqual(event["request_id"], response.json()["request_id"])
        self.assertEqual(event["status"], "rejected")
        self.assertIsNone(event["transaction_id"])
        self.assertEqual(event["committed_amount_cents"], 0)
        self.assertEqual(evidence["initial_snapshot"], evidence["final_snapshot"])
        self.assertEqual(evidence["ledger"], [])
        result = self.call("submit_refund", self.body, "invalid-then-fixed")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["amount_cents"], 333)
        self.assertEqual(self.call("submit_refund", self.body, "invalid-then-fixed").json(), result.json())
        self.assertEqual(len(self.evidence()["refunds"]), 1)

    def test_invalid_and_credential_headers_are_not_recorded_or_committed(self):
        other = self.new_session("tenant-other")
        unsafe = ["has spaces", "x" * 129, self.session["session_token"], self.admin_token,
                  other["session_token"], "prefix-" + other["session_token"], "sk-private-value", "Bearer.fake"]
        for invalid_body in (False, True):
            for header, field in (("X-Call-ID", "call_id"), ("Idempotency-Key", "idempotency_key")):
                for value in unsafe:
                    with self.subTest(header=header, invalid_body=invalid_body, shape=len(value)):
                        headers = {**self.headers, "X-Call-ID": "valid-call", "Idempotency-Key": "valid-key", header: value}
                        body = self.body if not invalid_body else {**self.body, "amount_cents": 9}
                        response = self.client.post(f"/api/v1/sessions/{self.sid}/tools/submit_refund", headers=headers, json=body)
                        self.reject(response, "INVALID_REQUEST", 422)
                        event = self.evidence()["events"][-1]
                        self.assertIsNone(event[field])
                        other_field = "idempotency_key" if field == "call_id" else "call_id"
                        self.assertEqual(event[other_field], "valid-key" if other_field == "idempotency_key" else "valid-call")
        evidence = self.evidence()
        self.assertEqual(evidence["refunds"], [])
        self.assertEqual(evidence["ledger"], [])
        for value in unsafe:
            self.assertNotIn(value, json.dumps(evidence))
        self.assertEqual(self.call("submit_refund", self.body, "valid-key").status_code, 200)

    def test_duplicate_transport_headers_are_rejected(self):
        for header in ("X-Call-ID", "Idempotency-Key"):
            headers = list({**self.headers, "X-Call-ID": "one-call", "Idempotency-Key": "one-key"}.items())
            headers.append((header, "second-value"))
            response = self.client.post(f"/api/v1/sessions/{self.sid}/tools/submit_refund", headers=headers, json=self.body)
            self.reject(response, "INVALID_REQUEST", 422)
            event = self.evidence()["events"][-1]
            self.assertIsNone(event["call_id" if header == "X-Call-ID" else "idempotency_key"])
        self.assertEqual(self.evidence()["refunds"], [])

    def test_unknown_tool_and_malformed_json_are_authenticated_rejected_facts(self):
        before = self.evidence()
        unknown = self.call("unknown_tool", {}, "unknown-key")
        self.reject(unknown, "NOT_FOUND", 404)
        headers = {**self.headers, "Content-Type": "application/json", "X-Call-ID": "malformed-call", "Idempotency-Key": "malformed-key"}
        malformed = self.client.post(f"/api/v1/sessions/{self.sid}/tools/submit_refund", headers=headers, content='{"items":')
        self.reject(malformed, "INVALID_REQUEST", 422)
        evidence = self.evidence()
        self.assertEqual(evidence["final_snapshot"], before["final_snapshot"])
        events = evidence["events"][len(before["events"]):]
        self.assertEqual(len(events), 2)
        self.assertEqual([e["call_id"] for e in events], ["call-test", "malformed-call"])
        self.assertEqual([e["idempotency_key"] for e in events], ["unknown-key", "malformed-key"])
        for event in events:
            self.assertEqual(event["status"], "rejected")
            self.assertIsNone(event["result"])
            self.assertIsNone(event["transaction_id"])
            self.assertIsNone(event["ticket_id"])
            self.assertEqual(event["committed_amount_cents"], 0)
        self.assertEqual(self.call("submit_refund", self.body, "malformed-key").status_code, 200)

    def test_unattributable_errors_never_pollute_target_session(self):
        other = self.new_session("tenant-b")
        other_sid = other["session"]["session_id"]
        target = f"/api/v1/admin/sessions/{other_sid}/evidence"
        before = self.client.get(target, headers=self.admin).json()
        for name, content in (("unknown_tool", "{}"), ("submit_refund", "{")):
            for headers, status in ((self.headers, 403), ({}, 401)):
                response = self.client.post(f"/api/v1/sessions/{other_sid}/tools/{name}", headers={**headers, "Content-Type": "application/json"}, content=content)
                self.assertEqual(response.status_code, status)
        after = self.client.get(target, headers=self.admin).json()
        self.assertEqual(before["events"], after["events"])
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM security_events").fetchone()[0], 4)

    def test_nonfinite_invalid_parameters_keep_evidence_readable(self):
        for numeric in ("NaN", "1e400"):
            text = json.dumps(self.body).replace('"quantity": 1', '"quantity": ' + numeric)
            response = self.client.post(f"/api/v1/sessions/{self.sid}/tools/submit_refund", headers={**self.headers, "Content-Type": "application/json", "X-Call-ID": "nonfinite", "Idempotency-Key": "nonfinite-key"}, content=text)
            self.reject(response, "INVALID_REQUEST", 422)
            evidence = self.evidence()
            self.assertEqual(evidence["events"][-1]["call_id"], "nonfinite")
            self.assertEqual(evidence["events"][-1]["raw_arguments"]["items"][0]["quantity"], "[NON_FINITE]")
        self.assertEqual(self.call("submit_refund", self.body, "nonfinite-key").status_code, 200)

    def test_execution_source_labels_propagate_without_claiming_model_execution(self):
        for source in ("scripted_test", "mock_agent", "observed_agent_execution"):
            response = self.client.post("/api/v1/sessions", headers=self.admin, json={"tenant_id": "label-test", "execution_source": source})
            self.assertEqual(response.status_code, 201)
            created = response.json()
            sid = created["session"]["session_id"]
            headers = {"Authorization": "Bearer " + created["session_token"]}
            self.assertEqual(self.call("get_case", {}, headers=headers, sid=sid).status_code, 200)
            body = {"category": "label_test_only", "missing_facts": ["No model was called"], "evidence_message_ids": [], "expected_version": 1}
            ticket = self.call("submit_human_review", body, "label-ticket", headers=headers, sid=sid)
            self.assertEqual(ticket.status_code, 200)
            evidence = self.client.get(f"/api/v1/admin/sessions/{sid}/evidence", headers=self.admin).json()
            sources = [evidence["sources"], ticket.json()["sources"]]
            sources += [evidence[key][part]["sources"] for key in ("initial_snapshot", "final_snapshot") for part in ("session", "case")]
            sources += [event["sources"] for event in evidence["events"]]
            self.assertTrue(all(item["execution_source"] == source for item in sources))
            self.assertNotIn("provider", evidence)
            self.assertNotIn("usage", evidence)

    def test_human_ticket_idempotency_finish_and_restart_without_money(self):
        before = self.evidence()
        body = self.review_body()
        response = self.call("submit_human_review", body, "review-key")
        self.assertEqual(response.status_code, 200, response.text)
        ticket = response.json()
        self.assertEqual(ticket["status"], "open")
        self.assertEqual((ticket["session_version_before"], ticket["session_version_after"]), (1, 2))
        self.assertEqual(self.call("submit_human_review", body, "review-key").json(), ticket)
        self.reject(self.call("submit_human_review", {**body, "category": "changed"}, "review-key"), "IDEMPOTENCY_CONFLICT")
        self.reject(self.call("submit_human_review", body, "new-key"), "STALE_STATE")
        self.reject(self.call("submit_refund", self.body, "review-key"), "IDEMPOTENCY_CONFLICT")
        finish = {"outcome": "escalated", "explanation": "Pending human work", "expected_version": 2}
        self.assertEqual(self.call("finish_case", finish, "finish-key").status_code, 200)
        self.reject(self.call("submit_human_review", {**body, "expected_version": 3}, "post-finish"), "SESSION_FINISHED")
        self.client.close()
        self.app = create_app(self.db, self.admin_token)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.assertEqual(self.call("submit_human_review", body, "review-key").json(), ticket)
        evidence = self.evidence()
        self.assertEqual(evidence["human_reviews"], [ticket])
        self.assertEqual(evidence["ledger"], before["ledger"])
        self.assertEqual(evidence["refunds"], before["refunds"])
        self.assertEqual(evidence["final_snapshot"]["orders"], before["final_snapshot"]["orders"])
        self.assertEqual(evidence["final_snapshot"]["merchant_balance_cents"], 1700)
        self.assertEqual(evidence["final_snapshot"]["customer_balance_cents"], 0)
        for event in evidence["events"]:
            self.assertIsNone(event["transaction_id"])
            self.assertEqual(event["committed_amount_cents"], 0)
        committed = [e for e in evidence["events"] if e["tool_name"] == "submit_human_review" and e["status"] == "succeeded"]
        self.assertEqual(len(committed), 1)
        self.assertEqual(committed[0]["ticket_id"], ticket["ticket_id"])
        self.assertFalse(set(ticket) & {"answer", "verdict", "loss", "gold", "decision"})

    def test_human_evidence_scope_and_extra_fields(self):
        other = self.new_session("tenant-other")
        sid = other["session"]["session_id"]
        case = self.call("get_case", {}, headers={"Authorization": "Bearer " + other["session_token"]}, sid=sid).json()
        body = self.review_body()
        for message_id in (case["messages"][0]["message_id"], "unknown-message"):
            self.reject(self.call("submit_human_review", {**body, "evidence_message_ids": [message_id]}, "scope"), "OBJECT_FORBIDDEN", 403)
        self.reject(self.call("submit_human_review", {**body, "evidence_message_ids": body["evidence_message_ids"] * 2}, "duplicate"), "DUPLICATE_EVIDENCE")
        for extra in ({"status": "approved"}, {"amount_cents": 500}, {"decision": "refund"}):
            self.reject(self.call("submit_human_review", {**body, **extra}, "extra"), "INVALID_REQUEST", 422)
        self.assertEqual(self.evidence()["human_reviews"], [])

    def test_ticket_event_failure_rolls_back_ticket_version_and_key(self):
        original = self.app.state.store._event
        def fault(*args, **kwargs):
            if args[2] == "submit_human_review" and args[6] == "succeeded":
                raise RuntimeError("test-only event failure")
            return original(*args, **kwargs)
        with patch.object(self.app.state.store, "_event", side_effect=fault):
            self.reject(self.call("submit_human_review", self.review_body(), "retry-after-rollback"), "INTERNAL_ERROR", 500)
        evidence = self.evidence()
        self.assertEqual(evidence["human_reviews"], [])
        self.assertEqual(evidence["initial_snapshot"], evidence["final_snapshot"])
        self.assertEqual(self.call("submit_human_review", self.review_body(), "retry-after-rollback").status_code, 200)
        self.assertEqual(len(self.evidence()["human_reviews"]), 1)

    def test_escalated_finish_is_still_only_a_declaration(self):
        body = {"outcome": "escalated", "explanation": "No ticket was created", "expected_version": 1}
        self.assertEqual(self.call("finish_case", body, "declare").status_code, 200)
        self.assertEqual(self.evidence()["human_reviews"], [])

    def test_different_keys_same_version_race_still_commits_once(self):
        barrier = threading.Barrier(2)
        def send(key):
            with TestClient(self.app) as client:
                barrier.wait(timeout=5)
                response = self.call("submit_refund", self.body, key, client=client)
                return response.status_code, response.json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, ("race-a", "race-b")))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(next(body["code"] for status, body in results if status == 409), "STALE_STATE")
        self.assertEqual(len(self.evidence()["ledger"]), 1)
        self.assertEqual(self.evidence()["refunds"][0]["amount_cents"], 333)

    def test_multiline_later_failure_rolls_back_and_corrected_same_key_succeeds(self):
        body = {**self.body, "confirmation_message_id": self.case["messages"][1]["message_id"],
                "items": [self.body["items"][0], {"item_id": self.order["items"][1]["item_id"], "quantity": 1}]}
        self.reject(self.call("submit_refund", body, "multiline"), "CONFIRMATION_SCOPE")
        evidence = self.evidence()
        self.assertEqual(evidence["initial_snapshot"], evidence["final_snapshot"])
        self.assertEqual(evidence["refunds"], [])
        self.assertEqual(self.call("submit_refund", self.body, "multiline").json()["amount_cents"], 333)


class MigrationTests(unittest.TestCase):
    def test_legacy_rows_and_successful_keys_survive_additive_migration(self):
        import tempfile
        Path("var").mkdir(exist_ok=True)
        original = json.loads(Path("artifacts/b_bootstrap/http_smoke/evidence_sample.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="migration-v1-", dir="var") as temp:
            database = str(Path(temp) / "legacy.sqlite3")
            token, admin = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            sid = original["final_snapshot"]["session"]["session_id"]
            with closing(sqlite3.connect(database)) as con, con:
                con.executescript(Path("migrations/001_initial.sql").read_text())
                con.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, hashlib.sha256(token.encode()).hexdigest(), json.dumps(original["initial_snapshot"]), json.dumps(original["final_snapshot"])))
                for refund in original["refunds"]:
                    con.execute("INSERT INTO refunds VALUES (?,?,?)", (refund["transaction_id"], sid, json.dumps(refund)))
                for entry in original["ledger"]:
                    con.execute("INSERT INTO ledger VALUES (?,?,?,?)", (entry["entry_id"], entry["transaction_id"], sid, json.dumps(entry)))
                for event in original["events"]:
                    con.execute("INSERT INTO events VALUES (?,?,?,?)", (sid, event["seq"], event["event_id"], json.dumps(event)))
                    if event["status"] == "succeeded" and event["tool_name"] in ("submit_refund", "finish_case"):
                        encoded = json.dumps({"tool": event["tool_name"], "arguments": event["validated_arguments"]}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                        con.execute("INSERT INTO requests VALUES (?,?,?,?)", (sid, event["idempotency_key"], hashlib.sha256(encoded.encode()).hexdigest(), json.dumps(event["result"])))
                tables = ("sessions", "refunds", "ledger", "requests", "events", "security_events")
                before = {table: con.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() for table in tables}
            app = create_app(database, admin)
            app.state.store.initialize()
            with closing(sqlite3.connect(database)) as con:
                for table in tables:
                    self.assertEqual(con.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall(), before[table])
                self.assertEqual(con.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall(), [(1,), (2,), (3,)])
                self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            with TestClient(app) as client:
                evidence = client.get(f"/api/v1/admin/sessions/{sid}/evidence", headers={"Authorization": "Bearer " + admin}).json()
                self.assertEqual(evidence["initial_snapshot"], original["initial_snapshot"])
                self.assertEqual(evidence["final_snapshot"], original["final_snapshot"])
                self.assertEqual(evidence["refunds"], original["refunds"])
                self.assertEqual(evidence["human_reviews"], [])
                self.assertEqual(evidence["schema_version"], 3)
                self.assertEqual(evidence["case_context_status"], "legacy_unavailable")
                self.assertIsNone(evidence["case_context"])
                refund_event = next(e for e in original["events"] if e["tool_name"] == "submit_refund" and e["status"] == "succeeded")
                retry = client.post(f"/api/v1/sessions/{sid}/tools/submit_refund", headers={"Authorization": "Bearer " + token, "Idempotency-Key": refund_event["idempotency_key"]}, json=refund_event["validated_arguments"])
                self.assertEqual(retry.status_code, 200)
                self.assertEqual(retry.json(), refund_event["result"])
                created = client.post("/api/v1/sessions", headers={"Authorization": "Bearer " + admin}, json={"tenant_id": "post-migration"}).json()
                new_sid = created["session"]["session_id"]
                ticket = client.post(f"/api/v1/sessions/{new_sid}/tools/submit_human_review", headers={"Authorization": "Bearer " + created["session_token"], "Idempotency-Key": "new-review"}, json={"category": "missing", "missing_facts": ["Review needed"], "evidence_message_ids": [], "expected_version": 1})
                self.assertEqual(ticket.status_code, 200)


if __name__ == "__main__":
    unittest.main()
