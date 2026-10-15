from copy import deepcopy
import json
from pathlib import Path
import secrets
import tempfile
import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from actuarial.claims import calculate_claim
from api.app import create_app
from contracts import models as m
from contracts.fixture_ids import GENERATED_FIXTURE_IDS
from evaluator.verify import claim_event, evaluate_evidence
from sandbox.case_generator import GeneratorError, build_library, load_config, write_library
from sandbox.fixture import REGISTRY, FixtureError, canonical_snapshot, load_fixture, validate_fixture

CONFIG = Path("configs/case_generator/b-cp2-v1.json")


class GeneratorDeterminismTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(CONFIG)

    def test_fixed_seed_is_byte_deterministic_and_counts_match_delivery_levels(self):
        first_files, first_registry, first_manifest = build_library(self.config)
        second_files, second_registry, second_manifest = build_library(deepcopy(self.config))
        self.assertEqual(first_files, second_files)
        self.assertEqual(first_registry, second_registry)
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(first_manifest["counts"], {
            "total": 40, "l0_regular": 8, "l0_stress": 4, "l1_regular": 24, "l1_stress": 4,
        })
        self.assertEqual(tuple(row["fixture_id"] for row in first_manifest["cases"]), GENERATED_FIXTURE_IDS)
        regular = [row for row in first_manifest["cases"] if row["level"] == "L1" and row["case_kind"] == "regular"]
        for category in ("whole-low", "whole-high", "partial-low", "partial-high"):
            rows = [row for row in regular if row["category"] == category]
            self.assertEqual(len(rows), 6)
            self.assertEqual(sum(row["split_candidate"] == "estimate_candidate" for row in rows), 3)
            self.assertEqual(sum(row["split_candidate"] == "holdout_candidate" for row in rows), 3)
        estimate = {row["family_id"] for row in regular if row["split_candidate"] == "estimate_candidate"}
        holdout = {row["family_id"] for row in regular if row["split_candidate"] == "holdout_candidate"}
        self.assertTrue(estimate.isdisjoint(holdout))
        self.assertTrue(all(row["known_net_loss_cents"] is None and row["insurance_payout_cents"] is None for row in first_manifest["cases"]))

    def test_seed_change_changes_business_facts_without_changing_allowlisted_ids(self):
        one = build_library(self.config)[2]
        changed = deepcopy(self.config)
        changed["seed"] = "agentshield-bcp2-public-seed-v2"
        two = build_library(changed)[2]
        self.assertEqual([row["fixture_id"] for row in one["cases"]], [row["fixture_id"] for row in two["cases"]])
        self.assertNotEqual([row["business_initial_hash"] for row in one["cases"]],
                            [row["business_initial_hash"] for row in two["cases"]])

    def test_invalid_config_is_atomic_and_leaves_no_partial_output(self):
        invalid = deepcopy(self.config)
        invalid["l1_regular_per_category"] = 5
        with tempfile.TemporaryDirectory(dir="var") as temp:
            root = Path(temp)
            with self.assertRaises(GeneratorError):
                write_library(invalid, root / "generated", root / "CASE_MANIFEST.json")
            self.assertFalse((root / "generated").exists())
            self.assertFalse((root / "CASE_MANIFEST.json").exists())


class FixtureSchemaCompatibilityTests(unittest.TestCase):
    def test_v1_templates_remain_compatible_and_v2_history_is_explicit(self):
        for fixture_id in ("dev-refund-v1", "dev-refund-v2"):
            raw = json.loads(Path("sandbox/fixtures", fixture_id + ".json").read_text(encoding="utf-8"))
            self.assertEqual(raw["fixture_schema_version"], 1)
            parsed = validate_fixture(raw)
            self.assertTrue(all(
                line["initial_refunded_quantity"] == line["initial_refunded_cents"] == 0
                and line["initial_refund_source"] is None
                for order in parsed["orders"] for line in order["items"]
            ))
        historical, _ = load_fixture("bcp2-l1-whole-low-04")
        self.assertEqual(historical["fixture_schema_version"], 2)
        history = [line for order in historical["orders"] for line in order["items"] if line["initial_refunded_quantity"]]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["initial_refund_source"], "pre_session_business_history")

    def test_v2_history_quantity_amount_and_opening_balances_conserve(self):
        fixture, _ = load_fixture("bcp2-l1-whole-low-04")
        canonical = canonical_snapshot(fixture)
        paid = sum(order["paid_cents"] for order in canonical["orders"])
        refunded = sum(order["refunded_cents"] for order in canonical["orders"])
        self.assertEqual(refunded, canonical["customer_balance_cents"])
        self.assertEqual(canonical["merchant_balance_cents"] + canonical["customer_balance_cents"], paid)
        for order in canonical["orders"]:
            self.assertEqual(order["remaining_cents"] + order["refunded_cents"], order["paid_cents"])
            for line in order["items"]:
                self.assertEqual(line["refundable_quantity"] + line["refunded_quantity"],
                                 line["quantity"] if line["eligible"] else line["refunded_quantity"])

    def test_invalid_v2_history_is_rejected_before_any_runtime_write(self):
        fixture, _ = load_fixture("bcp2-l1-whole-low-04")
        for mutation in ("amount", "source", "balance"):
            bad = deepcopy(fixture)
            line = bad["orders"][0]["items"][0]
            if mutation == "amount":
                line["initial_refunded_cents"] += 1
            elif mutation == "source":
                line["initial_refund_source"] = None
            else:
                bad["merchant_balance_cents"] += 1
            with self.subTest(mutation=mutation), self.assertRaises((FixtureError, ValidationError)):
                validate_fixture(bad)


class GeneratedFixtureHttpTests(unittest.TestCase):
    def setUp(self):
        Path("var").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir="var")
        self.admin_token = secrets.token_urlsafe(32)
        self.admin = {"Authorization": "Bearer " + self.admin_token}
        self.client = TestClient(create_app(Path(self.temp.name) / "test.sqlite3", self.admin_token), raise_server_exceptions=False)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def create(self, fixture_id, config_id="config-a"):
        response = self.client.post("/api/v1/sessions", headers=self.admin, json={
            "tenant_id": "generator-test", "fixture_id": fixture_id, "experiment_id": "bcp2-test",
            "config_id": config_id, "execution_source": "mock_agent",
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def call(self, created, name, body, key=None):
        headers = {"Authorization": "Bearer " + created["session_token"], "X-Call-ID": "generator-check"}
        if key:
            headers["Idempotency-Key"] = key
        return self.client.post(
            f"/api/v1/sessions/{created['session']['session_id']}/tools/{name}", headers=headers, json=body
        )

    def evidence(self, created):
        response = self.client.get(
            f"/api/v1/admin/sessions/{created['session']['session_id']}/evidence", headers=self.admin
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_same_case_across_configs_has_same_initial_hash_and_isolated_runtime(self):
        first = self.create("bcp2-l1-whole-low-01", "config-a")
        second = self.create("bcp2-l1-whole-low-01", "config-b")
        self.assertEqual(first["session"]["case_id"], second["session"]["case_id"])
        self.assertNotEqual(first["session"]["session_id"], second["session"]["session_id"])
        self.assertNotEqual(first["session"]["episode_id"], second["session"]["episode_id"])
        self.assertEqual(first["case_context"]["canonical_initial"], second["case_context"]["canonical_initial"])
        self.assertEqual(first["case_context"]["business_initial_hash"], second["case_context"]["business_initial_hash"])
        self.assertNotEqual(first["case_context"]["object_mapping"], second["case_context"]["object_mapping"])

    def test_opening_history_is_not_episode_transaction_and_cannot_be_refunded_twice(self):
        created = self.create("bcp2-l1-whole-low-04")
        case = self.call(created, "get_case", {}).json()
        order = self.call(created, "get_order", {"order_id": case["candidate_order_ids"][0]}).json()
        line = order["items"][0]
        self.assertEqual((line["quantity"], line["refunded_quantity"], line["refundable_quantity"]), (3, 1, 2))
        before = self.evidence(created)
        self.assertGreater(before["initial_snapshot"]["customer_balance_cents"], 0)
        self.assertEqual(before["refunds"], [])
        self.assertEqual(before["ledger"], [])
        self.assertFalse(any(event["tool_name"] == "submit_refund" for event in before["events"]))

        confirmation = next(message for message in case["messages"] if message["confirmation"])
        body = {
            "order_id": order["order_id"], "items": [{"item_id": line["item_id"], "quantity": 2}],
            "confirmation_message_id": confirmation["message_id"], "expected_version": 2,
            "reason": "只退款历史初态后的剩余两件",
        }
        committed = self.call(created, "submit_refund", body, "remaining-two")
        self.assertEqual(committed.status_code, 200, committed.text)
        duplicate = {**body, "items": [{"item_id": line["item_id"], "quantity": 1}], "expected_version": 3}
        rejected = self.call(created, "submit_refund", duplicate, "no-double-refund")
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.json()["code"], "QUANTITY_LIMIT")
        after = self.evidence(created)
        self.assertEqual(len(after["refunds"]), 1)
        self.assertEqual(len(after["ledger"]), 1)
        self.assertEqual(after["refunds"][0]["amount_cents"],
                         line["allocated_paid_cents"] - line["refunded_cents"])
        self.assertEqual(after["final_snapshot"]["customer_balance_cents"],
                         before["initial_snapshot"]["customer_balance_cents"] + after["refunds"][0]["amount_cents"])

    def test_c_reads_schema3_evidence_without_inventing_gold_loss_or_payout(self):
        created = self.create("bcp2-l0-whole-low-01")
        case = self.call(created, "get_case", {}).json()
        order = self.call(created, "get_order", {"order_id": case["candidate_order_ids"][0]}).json()
        confirmation = next(message for message in case["messages"] if message["confirmation"])
        body = {
            "order_id": order["order_id"],
            "items": [{"item_id": order["items"][0]["item_id"], "quantity": 1}],
            "confirmation_message_id": confirmation["message_id"], "expected_version": order["version"],
            "reason": "C Mock 新候选读取测试",
        }
        self.assertEqual(self.call(created, "submit_refund", body, "c-mock-case").status_code, 200)
        evidence = self.evidence(created)
        m.EvidenceBundle.model_validate(evidence)
        result = evaluate_evidence(evidence)
        self.assertEqual(result["loss_status"], "needs_review")
        self.assertIsNone(result["net_loss_cents"])
        contract = json.loads(Path("configs/insurance/research_contract_v0.1.json").read_text(encoding="utf-8"))
        claim = calculate_claim(claim_event(result), contract)
        self.assertEqual(claim["claim_status"], "needs_review")
        self.assertIsNone(claim["payout_cents"])

    def test_catalog_is_exact_fixed_allowlist_and_injection_routes_are_rejected(self):
        catalog = self.client.get("/api/v1/admin/fixtures", headers=self.admin)
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual([row["fixture_id"] for row in catalog.json()["fixtures"]], list(REGISTRY))
        self.assertEqual(tuple(REGISTRY)[2:], GENERATED_FIXTURE_IDS)
        for body in (
            {"tenant_id": "x", "fixture_id": "../generated/bcp2-l0-whole-low-01.json"},
            {"tenant_id": "x", "fixture_id": "https://example.invalid/case.json"},
            {"tenant_id": "x", "fixture_id": "unregistered"},
            {"tenant_id": "x", "fixture_path": "sandbox/fixtures/generated/bcp2-l0-whole-low-01.json"},
            {"tenant_id": "x", "fixture": {}},
        ):
            response = self.client.post("/api/v1/sessions", headers=self.admin, json=body)
            self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
