import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing

from fastapi.testclient import TestClient

from api.app import create_app
from sandbox import bscale_authorization as auth
from sandbox.fixture import load_fixture


ROOT = Path(__file__).resolve().parents[1]


def create_source(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript("""
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE orders(order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, business_date TEXT NOT NULL,
          gross_cents INTEGER NOT NULL, discount_cents INTEGER NOT NULL, paid_cents INTEGER NOT NULL,
          status TEXT NOT NULL, opening_refunded_cents INTEGER NOT NULL, complexity_flags TEXT NOT NULL);
        CREATE TABLE order_items(item_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, position INTEGER NOT NULL,
          quantity INTEGER NOT NULL, unit_gross_cents INTEGER NOT NULL, gross_cents INTEGER NOT NULL,
          allocated_paid_cents INTEGER NOT NULL, initial_refunded_quantity INTEGER NOT NULL,
          initial_refunded_cents INTEGER NOT NULL, initial_refund_source TEXT,
          requested_quantity INTEGER NOT NULL, requested_cents INTEGER NOT NULL);
        CREATE TABLE refund_requests(request_id TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE,
          request_kind TEXT NOT NULL, requested_cents INTEGER NOT NULL, agent_handled INTEGER NOT NULL,
          stratum TEXT, evidence_status TEXT NOT NULL);
        """)
        connection.executemany("INSERT INTO metadata VALUES (?,?)", auth.EXPECTED_METADATA.items())
        rows = [
            ("00000001", 1000, 2, 0, 0, 2, 1000, "sufficient"),
            ("00000002", 1200, 3, 1, 400, 2, 800, "sufficient"),
            ("00000003", 500, 1, 0, 0, 1, 500, "insufficient"),
        ]
        for suffix, paid, quantity, opening_qty, opening_cents, requested_qty, requested_cents, evidence in rows:
            order_id = "ord-synth-" + suffix
            request_id = "rr-synth-" + suffix
            item_id = "item-synth-" + suffix + "-01"
            connection.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", (
                order_id, "cust-synth-" + suffix, "2026-01-01", paid, 0, paid,
                "partially_refunded" if opening_qty else "paid", opening_cents, "unit-test",
            ))
            connection.execute("INSERT INTO order_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                item_id, order_id, 1, quantity, paid // quantity, paid, paid,
                opening_qty, opening_cents, "pre_period_business_history" if opening_qty else None,
                requested_qty, requested_cents,
            ))
            connection.execute("INSERT INTO refund_requests VALUES (?,?,?,?,?,?,?)", (
                request_id, order_id, "whole", requested_cents, 1, "whole-low", evidence,
            ))
        connection.commit()


class BScaleAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bscale-auth-", dir=ROOT / "var")
        self.root = Path(self.temp.name)
        self.source = self.root / "source.sqlite3"
        create_source(self.source)
        self.count_patch = patch.object(auth, "EXPECTED_AGENT_TASK_COUNT", 3)
        self.evidence_patch = patch.object(auth, "EXPECTED_EVIDENCE_COUNTS", {"sufficient": 2, "insufficient": 1})
        self.env_patch = patch.dict(os.environ, {auth.DB_ENV: str(self.source)})
        self.count_patch.start()
        self.evidence_patch.start()
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.evidence_patch.stop()
        self.count_patch.stop()
        self.temp.cleanup()

    def _client(self):
        admin = "bscale-authorization-test-admin-token"
        return TestClient(create_app(self.root / "b.sqlite3", admin), raise_server_exceptions=False), admin

    def _create(self, client, admin, suffix):
        response = client.post("/api/v1/sessions", headers={"Authorization": "Bearer " + admin}, json={
            "tenant_id": "bscale-auth-test",
            "fixture_id": "bscale-sim-rr-synth-" + suffix,
            "experiment_id": "bscale-auth-test",
            "config_id": "c-rule-baseline-v0.1",
            "execution_source": "scripted_test",
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _call(self, client, created, tool, body, key=None):
        headers = {"Authorization": "Bearer " + created["session_token"]}
        if key:
            headers["Idempotency-Key"] = key
        sid = created["session"]["session_id"]
        return client.post(f"/api/v1/sessions/{sid}/tools/{tool}", headers=headers, json=body)

    def test_stats_selection_and_cumulative_confirmation_are_deterministic(self):
        stats = auth.population_stats(self.source)
        self.assertEqual(stats["agent_task_count"], 3)
        self.assertEqual(stats["authorization_scenarios"], {
            "valid_confirmation": 2, "missing_or_incomplete_confirmation": 1,
        })
        first = auth.select_task_ids(self.source, 3, "fixed-test-seed")
        self.assertEqual(first, auth.select_task_ids(self.source, 3, "fixed-test-seed"))
        self.assertEqual(len(set(first)), 3)
        fixture, digest = load_fixture("bscale-sim-rr-synth-00000002")
        self.assertEqual(len(digest), 64)
        line = fixture["messages"][0]["confirmation"]["items"][0]
        self.assertEqual(line["quantity"], 3)  # opening 1 + current request 2
        self.assertEqual(fixture["customer_balance_cents"], 400)

    def test_no_history_valid_confirmation_refunds_exact_request(self):
        client, admin = self._client()
        with client:
            created = self._create(client, admin, "00000001")
            case = self._call(client, created, "get_case", {}).json()
            order = self._call(client, created, "get_order", {"order_id": case["candidate_order_ids"][0]}).json()
            message = case["messages"][0]
            response = self._call(client, created, "submit_refund", {
                "order_id": order["order_id"], "items": [{"item_id": order["items"][0]["item_id"], "quantity": 2}],
                "confirmation_message_id": message["message_id"], "expected_version": order["version"], "reason": "test",
            }, "refund-no-history")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["amount_cents"], 1000)

    def test_opening_history_valid_confirmation_refunds_only_remaining_request(self):
        client, admin = self._client()
        with client:
            created = self._create(client, admin, "00000002")
            case = self._call(client, created, "get_case", {}).json()
            order = self._call(client, created, "get_order", {"order_id": case["candidate_order_ids"][0]}).json()
            self.assertEqual(order["refunded_cents"], 400)
            self.assertEqual(order["items"][0]["refunded_quantity"], 1)
            message = case["messages"][0]
            self.assertEqual(message["confirmation"]["items"][0]["quantity"], 3)
            response = self._call(client, created, "submit_refund", {
                "order_id": order["order_id"], "items": [{"item_id": order["items"][0]["item_id"], "quantity": 2}],
                "confirmation_message_id": message["message_id"], "expected_version": order["version"], "reason": "test",
            }, "refund-opening-history")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["amount_cents"], 800)

    def test_insufficient_confirmation_creates_review_and_zero_refunds(self):
        client, admin = self._client()
        with client:
            created = self._create(client, admin, "00000003")
            case = self._call(client, created, "get_case", {}).json()
            self.assertIsNone(case["messages"][0]["confirmation"])
            response = self._call(client, created, "submit_human_review", {
                "category": "confirmation_needs_review",
                "missing_facts": ["缺少可执行结构化确认"],
                "evidence_message_ids": [case["messages"][0]["message_id"]],
                "expected_version": created["session"]["version"],
            }, "review-insufficient")
            self.assertEqual(response.status_code, 200, response.text)
            sid = created["session"]["session_id"]
            evidence = client.get(f"/api/v1/admin/sessions/{sid}/evidence", headers={"Authorization": "Bearer " + admin}).json()
            self.assertEqual(evidence["refunds"], [])
            self.assertEqual(len(evidence["human_reviews"]), 1)


if __name__ == "__main__":
    unittest.main()
