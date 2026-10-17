from contextlib import closing
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.app import create_app
from contracts import models as m
from sandbox import fixture as f
from tests import test_backend as baseline


def canonical_from_http(evidence):
    """Independent consumer projection: uses only returned JSON, no Store internals."""
    result = deepcopy(evidence["initial_snapshot"])
    context = evidence["case_context"]
    inverse = {kind: {v: k for k, v in mapping.items()} for kind, mapping in context["object_mapping"].items()}
    result.pop("session")
    case = result["case"]
    case.pop("case_id")
    case.pop("sources")
    case["customer_id"] = inverse["customers"][case["customer_id"]]
    case["candidate_order_ids"] = [inverse["orders"][oid] for oid in case["candidate_order_ids"]]
    for message in case["messages"]:
        message["message_id"] = inverse["messages"][message["message_id"]]
        message["customer_id"] = inverse["customers"][message["customer_id"]]
        if message["confirmation"]:
            message["confirmation"]["order_id"] = inverse["orders"][message["confirmation"]["order_id"]]
            for line in message["confirmation"]["items"]:
                line["item_id"] = inverse["items"][line["item_id"]]
    for order in result["orders"]:
        order["order_id"] = inverse["orders"][order["order_id"]]
        order["customer_id"] = inverse["customers"][order["customer_id"]]
        order["tenant_id"] = "template-tenant"
        for line in order["items"]:
            line["item_id"] = inverse["items"][line["item_id"]]
    result.update(canonical_version="business-initial-v1", environment_version=context["environment_version"],
                  business_time=context["canonical_initial"]["business_time"])
    return result


class CaseFixtureTests(unittest.TestCase):
    setUp = baseline.BackendTests.setUp
    tearDown = baseline.BackendTests.tearDown
    new_session = baseline.BackendTests.new_session
    call = baseline.BackendTests.call
    evidence = baseline.BackendTests.evidence
    reject = baseline.BackendTests.reject

    def create(self, **args):
        response = self.client.post("/api/v1/sessions", headers=self.admin, json={"tenant_id": "case-test", **args})
        self.assertEqual(response.status_code, 201, response.status_code)
        return response.json()

    def facts(self, created):
        response = self.client.get(f"/api/v1/admin/sessions/{created['session']['session_id']}/evidence", headers=self.admin)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def rows(self):
        with self.app.state.store.transaction() as con:
            return {name: [tuple(row) for row in con.execute(f"SELECT * FROM {name} ORDER BY rowid")]
                    for name in ("sessions", "session_cases", "requests", "refunds", "ledger", "human_reviews", "events")}

    def test_same_case_across_configs_has_equal_business_initial_and_disjoint_runtime_ids(self):
        other = self.create(tenant_id="another-tenant", config_id="candidate-b", experiment_id="experiment-b", execution_source="mock_agent")
        first, second = self.evidence(), self.facts(other)
        self.assertEqual(self.session["session"]["case_id"], other["session"]["case_id"])
        self.assertNotEqual(self.sid, other["session"]["session_id"])
        self.assertNotEqual(self.session["session"]["episode_id"], other["session"]["episode_id"])
        one, two = first["case_context"], second["case_context"]
        self.assertEqual(one["case_id"], one["source_case_id"])
        self.assertEqual(one["canonical_initial"], two["canonical_initial"])
        self.assertEqual(one["business_initial_hash"], two["business_initial_hash"])
        self.assertEqual(one["business_initial_hash"], "9b523072ae8198c91bd4945b7735b5f59ee048f269695ed493eec0e96936271b")
        for kind in ("customers", "orders", "items", "messages"):
            self.assertEqual(set(one["object_mapping"][kind]), set(two["object_mapping"][kind]))
            self.assertTrue(set(one["object_mapping"][kind].values()).isdisjoint(two["object_mapping"][kind].values()))
        self.assertEqual(self.call("submit_refund", self.body, "same-case-isolated").json()["amount_cents"], 333)
        second_after = self.facts(other)
        self.assertEqual(second_after["initial_snapshot"], second_after["final_snapshot"])
        self.assertEqual(second_after["refunds"], [])
        self.assertEqual(self.evidence()["case_context"], one)

    def test_same_case_does_not_authorize_other_session_objects_or_tokens(self):
        other = self.create(tenant_id="tenant-a")
        facts = self.facts(other)
        order = facts["initial_snapshot"]["orders"][0]
        self.reject(self.call("get_order", {"order_id": order["order_id"]}), "OBJECT_FORBIDDEN", 403)
        self.reject(self.call("submit_refund", {**self.body, "order_id": order["order_id"]}, "foreign-order"), "OBJECT_FORBIDDEN", 403)
        self.reject(self.call("submit_human_review", {"category": "scope", "missing_facts": ["missing"],
                    "evidence_message_ids": [facts["initial_snapshot"]["case"]["messages"][0]["message_id"]],
                    "expected_version": 1}, "foreign-message"), "OBJECT_FORBIDDEN", 403)
        self.reject(self.call("get_case", {}, sid=other["session"]["session_id"]), "FORBIDDEN", 403)
        self.assertEqual(self.facts(other)["events"], [])
        self.assertEqual(self.evidence()["refunds"], [])

    def test_public_mapping_reconstructs_canonical_and_links_committed_facts(self):
        self.call("submit_refund", self.body, "mapped-refund")
        evidence = self.evidence()
        canonical = canonical_from_http(evidence)
        self.assertEqual(canonical, evidence["case_context"]["canonical_initial"])
        digest = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
        self.assertEqual(digest, evidence["case_context"]["business_initial_hash"])
        mapping = evidence["case_context"]["object_mapping"]
        refund = evidence["refunds"][0]
        self.assertEqual(refund["order_id"], mapping["orders"]["order-1"])
        self.assertEqual(refund["items"][0]["item_id"], mapping["items"]["item-1"])
        self.assertEqual(refund["confirmation_message_id"], mapping["messages"]["message-all"])
        self.assertEqual(refund["amount_cents"], 333)
        encoded = json.dumps(canonical)
        for excluded in (self.sid, self.session["session_token"], self.admin_token, self.session["session"]["episode_id"]):
            self.assertNotIn(excluded, encoded)

    def test_second_fixture_structural_difference_and_quantity_confirmation_controls(self):
        created = self.create(fixture_id="dev-refund-v2")
        facts = self.facts(created)
        context = facts["case_context"]
        self.assertNotEqual(context["case_id"], self.case["case_id"])
        self.assertNotEqual(context["business_initial_hash"], self.session["case_context"]["business_initial_hash"])
        self.assertEqual(canonical_from_http(facts), context["canonical_initial"])
        self.assertEqual(len(facts["initial_snapshot"]["orders"]), 1)
        self.assertEqual(len(facts["initial_snapshot"]["orders"][0]["items"]), 3)
        self.assertEqual(len(facts["initial_snapshot"]["case"]["messages"]), 2)
        self.assertIsNone(facts["initial_snapshot"]["case"]["messages"][0]["confirmation"])
        mapping = context["object_mapping"]
        kwargs = {"sid": created["session"]["session_id"], "headers": {"Authorization": "Bearer " + created["session_token"]}}
        body = {"order_id": mapping["orders"]["order-bundle"], "items": [{"item_id": mapping["items"]["item-cup"], "quantity": 1}],
                "confirmation_message_id": mapping["messages"]["message-question"], "expected_version": 1, "reason": "Second engineering template"}
        self.reject(self.call("submit_refund", body, "v2", **kwargs), "CONFIRMATION_SCOPE")
        body["confirmation_message_id"] = mapping["messages"]["message-confirm"]
        refund = self.call("submit_refund", body, "v2", **kwargs).json()
        self.assertEqual(refund["amount_cents"], 250)
        self.assertEqual(self.call("submit_refund", body, "v2", **kwargs).json(), refund)
        too_many = {**body, "expected_version": 2, "items": [{"item_id": mapping["items"]["item-coaster"], "quantity": 3}]}
        self.reject(self.call("submit_refund", too_many, "quantity", **kwargs), "CONFIRMATION_SCOPE")
        ineligible = {**body, "expected_version": 2, "items": [{"item_id": mapping["items"]["item-bag"], "quantity": 1}]}
        self.reject(self.call("submit_refund", ineligible, "ineligible", **kwargs), "NOT_ELIGIBLE")
        final = self.facts(created)
        self.assertEqual(len(final["refunds"]), 1)
        self.assertEqual((final["final_snapshot"]["merchant_balance_cents"], final["final_snapshot"]["customer_balance_cents"]), (751, 250))

    def test_unregistered_paths_inline_templates_and_agent_registration_rejected(self):
        before = self.rows()
        for extra in ({"fixture_id": "../dev-refund-v1.json"}, {"fixture_id": "https://example.invalid/task.json"},
                      {"fixture_id": "not-registered"}, {"fixture_path": "sandbox/fixtures/dev-refund-v1.json"},
                      {"fixture": {}}, {"case_id": "override"}, {"source_case_id": "override"}):
            self.reject(self.client.post("/api/v1/sessions", headers=self.admin, json={"tenant_id": "x", **extra}), "INVALID_REQUEST", 422)
        self.reject(self.client.post("/api/v1/sessions", headers=self.headers, json={"tenant_id": "x"}), "FORBIDDEN", 403)
        self.assertEqual(self.rows(), before)

    def test_invalid_registered_templates_leave_no_partial_business_rows(self):
        original = json.loads(Path("sandbox/fixtures/dev-refund-v1.json").read_text(encoding="utf-8"))
        mutations = [
            (("orders", 0, "paid_cents"), -1), (("orders", 0, "paid_cents"), 999999),
            (("orders", 0, "items", 0, "quantity"), True), (("orders", 0, "items", 0, "quantity"), 1.5),
            (("orders", 0, "items", 0, "quantity"), 0), (("orders", 0, "items", 0, "eligible"), "true"),
            (("orders", 0, "items", 0, "allocated_paid_cents"), 999),
            (("orders", 1, "order_id"), "order-1"), (("orders", 1, "items", 0, "item_id"), "item-1"),
            (("messages", 1, "message_id"), "message-all"), (("messages", 0, "customer_id"), "foreign"),
            (("messages", 0, "confirmation", "order_id"), "missing"),
            (("messages", 0, "confirmation", "items", 0, "item_id"), "item-3"),
            (("messages", 0, "confirmation", "items", 0, "quantity"), 4),
            (("messages", 0, "confirmation", "items", 1, "item_id"), "item-1"),
            (("candidate_order_ids",), ["order-1"]), (("merchant_balance_cents",), 1701),
            (("customer_balance_cents",), False), (("source_case_id",), "unregistered-case"),
            (("fixture_version",), "unregistered-version"), (("policy", "allocation_version"), "unknown"),
            (("fixture_source",), "formal_gold"), (("gold",), {"answer": "must-not-load"}),
        ]
        before = self.rows()
        with tempfile.TemporaryDirectory(prefix="invalid-fixture-", dir="var") as temp, patch.object(f, "FIXTURE_ROOT", Path(temp)):
            path = Path(temp) / "dev-refund-v1.json"
            for keys, value in mutations:
                with self.subTest(keys=keys, value=value):
                    data = deepcopy(original)
                    target = data
                    for key in keys[:-1]: target = target[key]
                    target[keys[-1]] = value
                    path.write_text(json.dumps(data), encoding="utf-8")
                    response = self.client.post("/api/v1/sessions", headers=self.admin, json={"tenant_id": "invalid"})
                    self.reject(response, "INVALID_FIXTURE", 422)
                    self.assertNotIn(temp, response.text)
                    self.assertEqual(self.rows(), before)

    def test_bad_json_missing_file_and_outside_registered_directory_are_atomic(self):
        before = self.rows()
        with tempfile.TemporaryDirectory(prefix="json-fixture-", dir="var") as temp, patch.object(f, "FIXTURE_ROOT", Path(temp)):
            path = Path(temp) / "dev-refund-v1.json"
            for data in ('{"a":1,"a":2}', '{"a":NaN}', '{', ' ' * 512001):
                path.write_text(data, encoding="utf-8")
                self.reject(self.client.post("/api/v1/sessions", headers=self.admin, json={"tenant_id": "invalid"}), "INVALID_FIXTURE", 422)
            # A registered filename cannot escape the trusted directory, even through local registration mistakes.
            with patch.object(f, "REGISTRY", {"dev-refund-v1": ("../missing.json", "dev-case-refund-v1", "dev-refund-v1-r1")}):
                self.reject(self.client.post("/api/v1/sessions", headers=self.admin, json={"tenant_id": "invalid"}), "INVALID_FIXTURE", 422)
            self.reject(self.client.post("/api/v1/sessions", headers=self.admin, json={"tenant_id": "invalid", "fixture_id": "dev-refund-v2"}), "INVALID_FIXTURE", 422)
        self.assertEqual(self.rows(), before)

    def test_context_insert_failure_rolls_back_session_creation(self):
        before = self.rows()
        with patch.object(self.app.state.store, "_insert_case_context", side_effect=sqlite3.OperationalError("test fault")):
            self.reject(self.client.post("/api/v1/sessions", headers=self.admin, json={"tenant_id": "rollback"}), "INTERNAL_ERROR", 500)
        self.assertEqual(self.rows(), before)

    def test_frozen_context_does_not_reload_changed_template_on_read_or_restart(self):
        initial = self.evidence()["case_context"]
        with patch.object(f, "load_fixture", side_effect=f.FixtureError("template unavailable")):
            self.assertEqual(self.evidence()["case_context"], initial)
            refund = self.call("submit_refund", self.body, "frozen").json()
            self.assertEqual(refund["amount_cents"], 333)
            with TestClient(create_app(self.db, self.admin_token)) as client:
                self.assertEqual(self.call("submit_refund", self.body, "frozen", client=client).json(), refund)
                evidence = client.get(f"/api/v1/admin/sessions/{self.sid}/evidence", headers=self.admin).json()
                self.assertEqual(evidence["case_context"], initial)


class CanonicalValidationTests(unittest.TestCase):
    def test_business_changes_change_hash_and_metadata_does_not(self):
        original, _ = f.load_fixture("dev-refund-v1")
        expected = f.business_hash(f.canonical_snapshot(original))
        for key in ("notice", "family_id", "source_case_id", "fixture_version"):
            modified = deepcopy(original); modified[key] = "different"
            self.assertEqual(f.business_hash(f.canonical_snapshot(modified)), expected)
        for keys, value in [(("request",), "Different public request"), (("orders", 0, "items", 0, "eligible"), False),
                            (("messages", 0, "text"), "Different public message"),
                            (("messages", 0, "confirmation", "items", 0, "quantity"), 2),
                            (("policy", "rules", 0), "Different public rule"), (("policy", "policy_version"), "dev-new"),
                            (("business_time",), "2026-10-12T12:00:00+08:00"),
                            (("candidate_order_ids",), ["order-2", "order-1"])]:
            with self.subTest(keys=keys):
                modified = deepcopy(original); target = modified
                for key in keys[:-1]: target = target[key]
                target[keys[-1]] = value
                modified = f.validate_fixture(modified)
                self.assertNotEqual(f.business_hash(f.canonical_snapshot(modified)), expected)
        canonical = f.canonical_snapshot(original)
        # A constant hash or an order-dependent dictionary serialization cannot satisfy these.
        self.assertEqual(f.business_hash(dict(reversed(list(canonical.items())))), expected)
        changed = deepcopy(canonical); changed["orders"][0]["items"][0]["allocated_paid_cents"] += 1
        self.assertNotEqual(f.business_hash(changed), expected)

    def test_tail_allocation_uses_stable_template_ids_and_rejects_wrong_declared_tail(self):
        data, _ = f.load_fixture("dev-refund-v2")
        self.assertEqual([line["allocated_paid_cents"] for line in data["orders"][0]["items"]], [500, 300, 201])
        data["orders"][0]["items"][0]["allocated_paid_cents"] += 1
        data["orders"][0]["items"][1]["allocated_paid_cents"] -= 1
        with self.assertRaises(f.FixtureError): f.validate_fixture(data)
        self.assertEqual(f.allocate(1, [{"item_id": "z", "gross_cents": 1}, {"item_id": "a", "gross_cents": 1}]), {"z": 0, "a": 1})

    def test_registry_matches_create_contract_and_legacy_evidence_still_parses(self):
        fixture_schema = m.CreateSession.model_json_schema()["properties"]["fixture_id"]
        static_branch = next(branch for branch in fixture_schema["anyOf"] if "enum" in branch)
        dynamic_branch = next(branch for branch in fixture_schema["anyOf"] if "pattern" in branch)
        self.assertEqual(set(f.REGISTRY), set(static_branch["enum"]))
        self.assertEqual(dynamic_branch["pattern"], r"^bscale-sim-rr-synth-[0-9]{8}$")
        identities = [f.load_fixture(name)[0]["source_case_id"] for name in f.REGISTRY]
        self.assertEqual(len(identities), len(set(identities)))
        for filename in ("artifacts/b_bootstrap/http_smoke/evidence_sample.json", "artifacts/pro_bd_sprint/01/patch_http_evidence/evidence_sample.json"):
            legacy = json.loads(Path(filename).read_text(encoding="utf-8"))
            parsed = m.EvidenceBundle.model_validate(legacy)
            self.assertEqual(parsed.case_context_status, "legacy_unavailable")
            self.assertIsNone(parsed.case_context)
            self.assertEqual(parsed.initial_snapshot.model_dump(), legacy["initial_snapshot"])


class LegacyV2MigrationTests(unittest.TestCase):
    def test_v2_refund_ticket_finish_replay_preserves_original_rows_and_legacy_case_id(self):
        original = json.loads(Path("artifacts/pro_bd_sprint/01/patch_http_evidence/evidence_sample.json").read_text(encoding="utf-8"))
        Path("var").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="migration-v2-", dir="var") as temp:
            database = str(Path(temp) / "legacy.sqlite3")
            token, admin = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            sid = original["final_snapshot"]["session"]["session_id"]
            successful = [event for event in original["events"] if event["status"] == "succeeded" and event["tool_name"] in ("submit_refund", "submit_human_review", "finish_case")]
            self.assertEqual(len(successful), 3)
            tables = ("sessions", "refunds", "ledger", "requests", "events", "security_events", "human_reviews")
            with closing(sqlite3.connect(database)) as con, con:
                for sql in ("001_initial.sql", "002_human_reviews.sql"):
                    con.executescript(Path("migrations", sql).read_text())
                con.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, hashlib.sha256(token.encode()).hexdigest(), json.dumps(original["initial_snapshot"]), json.dumps(original["final_snapshot"])))
                for row in original["refunds"]: con.execute("INSERT INTO refunds VALUES (?,?,?)", (row["transaction_id"], sid, json.dumps(row)))
                for row in original["ledger"]: con.execute("INSERT INTO ledger VALUES (?,?,?,?)", (row["entry_id"], row["transaction_id"], sid, json.dumps(row)))
                for row in original["human_reviews"]: con.execute("INSERT INTO human_reviews VALUES (?,?,?)", (row["ticket_id"], sid, json.dumps(row)))
                for row in original["events"]: con.execute("INSERT INTO events VALUES (?,?,?,?)", (sid, row["seq"], row["event_id"], json.dumps(row)))
                for event in successful:
                    fingerprint = hashlib.sha256(json.dumps({"tool": event["tool_name"], "arguments": event["validated_arguments"]}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    con.execute("INSERT INTO requests VALUES (?,?,?,?)", (sid, event["idempotency_key"], fingerprint, json.dumps(event["result"])))
                before = {table: con.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() for table in tables}
            app = create_app(database, admin); app.state.store.initialize()
            with closing(sqlite3.connect(database)) as con:
                for table in tables: self.assertEqual(con.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall(), before[table])
                self.assertEqual(con.execute("SELECT * FROM session_cases").fetchall(), [])
                self.assertEqual(con.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall(), [(1,), (2,), (3,)])
                self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            with TestClient(app) as client:
                for event in successful:
                    response = client.post(f"/api/v1/sessions/{sid}/tools/{event['tool_name']}", headers={"Authorization": "Bearer " + token, "Idempotency-Key": event["idempotency_key"]}, json=event["validated_arguments"])
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), event["result"])
                evidence = client.get(f"/api/v1/admin/sessions/{sid}/evidence", headers={"Authorization": "Bearer " + admin}).json()
                for key in ("initial_snapshot", "final_snapshot", "refunds", "ledger", "human_reviews"):
                    self.assertEqual(evidence[key], original[key])
                self.assertEqual(evidence["events"][:len(original["events"])], original["events"])
                self.assertTrue(all(e["case_id"] == original["final_snapshot"]["session"]["case_id"] for e in evidence["events"]))
                self.assertEqual(evidence["schema_version"], 3)
                self.assertEqual(evidence["case_context_status"], "legacy_unavailable")
                self.assertIsNone(evidence["case_context"])


if __name__ == "__main__":
    unittest.main()
