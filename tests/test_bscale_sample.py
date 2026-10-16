import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from api.app import create_app
from contracts.fixture_ids import BSCALE_SAMPLE_FIXTURE_IDS
from sandbox.fixture import REGISTRY, load_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ID = "bscale-r1-rr-synth-00041076"
SOURCE_RECORD = ROOT / "sandbox" / "fixtures" / "bscale" / "source_record.json"


class BScaleSampleTests(unittest.TestCase):
    def test_first_draw_and_source_facts_are_pinned(self):
        record = json.loads(SOURCE_RECORD.read_text(encoding="utf-8"))
        selection = record["selection"]
        digest = hashlib.sha256(selection["seed"].encode("utf-8")).digest()
        self.assertEqual(selection["seed_sha256"], digest.hex())
        self.assertEqual(selection["zero_based_index"], int.from_bytes(digest, "big") % selection["pool_count"])
        self.assertEqual(selection["pool_count"], 6105)
        self.assertEqual(selection["redraw_count"], 0)
        self.assertEqual(selection["first_draw_conversion_status"], "converted")
        self.assertEqual(record["source_task"]["request_id"], "rr-synth-00041076")
        self.assertEqual(record["source_task"]["order_id"], record["source_order"]["order_id"])
        self.assertEqual(record["source_task"]["requested_cents"], sum(row["requested_cents"] for row in record["source_items"]))
        self.assertEqual(record["source_order"]["paid_cents"], sum(row["allocated_paid_cents"] for row in record["source_items"]))
        self.assertEqual(record["source_order"]["opening_refunded_cents"], sum(row["initial_refunded_cents"] for row in record["source_items"]))
        self.assertEqual(record["population"]["population_content_sha256"], "22978f7103eb84ce62f0b677bfb800279bfaf251f2b4708c121eddce80cee5a4")

    def test_fixture_preserves_money_and_does_not_invent_confirmation(self):
        self.assertEqual(BSCALE_SAMPLE_FIXTURE_IDS, (FIXTURE_ID,))
        self.assertIn(FIXTURE_ID, REGISTRY)
        fixture, digest = load_fixture(FIXTURE_ID)
        record = json.loads(SOURCE_RECORD.read_text(encoding="utf-8"))
        self.assertEqual(digest, record["conversion"]["fixture_content_sha256"])
        self.assertEqual(fixture["source_case_id"], "BSCALE-RR-SYNTH-00041076")
        self.assertEqual(fixture["customer_id"], record["source_order"]["customer_id"])
        self.assertEqual(fixture["orders"][0]["order_id"], record["source_order"]["order_id"])
        self.assertEqual(fixture["orders"][0]["paid_cents"], record["source_order"]["paid_cents"])
        self.assertEqual(fixture["merchant_balance_cents"], 7301)
        self.assertEqual(fixture["customer_balance_cents"], 0)
        self.assertEqual(fixture["messages"], [])
        self.assertIn("no customer message or structured confirmation", record["conversion"]["authorization_mapping"])

    def test_isolated_http_session_exposes_the_sample_without_money_movement(self):
        admin_token = "bscale-sample-admin-token-20261017"
        with tempfile.TemporaryDirectory(prefix="bscale-sample-", dir=ROOT / "var") as raw:
            app = create_app(Path(raw) / "b.sqlite3", admin_token)
            with TestClient(app, raise_server_exceptions=False) as client:
                admin = {"Authorization": "Bearer " + admin_token}
                response = client.post("/api/v1/sessions", headers=admin, json={
                    "tenant_id": "bscale-sample-c-handoff",
                    "fixture_id": FIXTURE_ID,
                    "experiment_id": "bscale-random-one-development",
                    "config_id": "c-rule-baseline-v0.1",
                    "execution_source": "scripted_test",
                })
                self.assertEqual(response.status_code, 201, response.text)
                created = response.json()
                sid = created["session"]["session_id"]
                session = {"Authorization": "Bearer " + created["session_token"]}
                case = client.post(f"/api/v1/sessions/{sid}/tools/get_case", headers=session, json={})
                self.assertEqual(case.status_code, 200, case.text)
                case_body = case.json()
                self.assertEqual(case_body["case_id"], "BSCALE-RR-SYNTH-00041076")
                self.assertEqual(case_body["messages"], [])
                order_id = case_body["candidate_order_ids"][0]
                order = client.post(f"/api/v1/sessions/{sid}/tools/get_order", headers=session, json={"order_id": order_id})
                self.assertEqual(order.status_code, 200, order.text)
                self.assertEqual(order.json()["paid_cents"], 7301)
                self.assertEqual(order.json()["refunded_cents"], 0)
                history = client.post(f"/api/v1/sessions/{sid}/tools/get_refund_history", headers=session, json={"order_id": order_id})
                self.assertEqual(history.status_code, 200, history.text)
                self.assertEqual(history.json()["refunds"], [])
                evidence = client.get(f"/api/v1/admin/sessions/{sid}/evidence", headers=admin)
                self.assertEqual(evidence.status_code, 200, evidence.text)
                self.assertEqual(evidence.json()["ledger"], [])
                self.assertEqual(evidence.json()["refunds"], [])


if __name__ == "__main__":
    unittest.main()
