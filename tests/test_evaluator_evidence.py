"""C evidence adapter against B's recorded examples; obligation specs here are synthetic test inputs, not Gold."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from evaluator.evidence_adapter import extract_facts, parse_bundle
from evaluator.export_schema import TARGET, render
from evaluator.obligations import SPEC_VERSION, SpecError
from evaluator.verify import evaluate_evidence

ROOT = Path(__file__).resolve().parents[1]
V1 = json.loads((ROOT / "contracts/evidence_example.json").read_text(encoding="utf-8"))
V2 = json.loads((ROOT / "contracts/fixture_v2_evidence_example.json").read_text(encoding="utf-8"))
LEGACY = json.loads((ROOT / "artifacts/b_bootstrap/http_smoke/evidence_sample.json").read_text(encoding="utf-8"))


def spec_for(bundle, obligations, **extra):
    context = bundle["case_context"]
    spec = {"spec_version": SPEC_VERSION, "spec_id": "synthetic-test-only", "case_id": context["case_id"],
            "fixture_id": context["fixture_id"], "fixture_version": context["fixture_version"],
            "policy_version": context["policy_version"], "source": "synthetic_test_only", "review_status": "not_reviewed",
            "closed_world": True, "obligations": obligations, "recovery": {"policy": "none_in_sandbox"},
            "coverage_status_input": "covered", "allowed_outcomes": [], "horizon": "test"}
    spec.update(extra)
    return spec


class EvidenceAdapterTests(unittest.TestCase):
    def test_recovers_333_and_250_cent_commits_with_ledger_checks(self):
        for bundle, cents, template_item in ((V1, 333, "item-1"), (V2, 250, "item-cup")):
            with self.subTest(case=bundle["case_context"]["case_id"]):
                facts = extract_facts(parse_bundle(bundle))
                self.assertEqual(facts["total_committed_cents"], cents)
                self.assertEqual(facts["ledger_checks"]["issues"], [])
                (order_item, slot), = facts["committed"].items()
                self.assertEqual(facts["reverse_items"][order_item[1]], template_item)
                self.assertEqual(slot["committed_cents"], cents)
                self.assertIsNotNone(slot["evidence"][0]["event_seq"])

    def test_without_spec_money_is_reported_but_not_judged(self):
        result = evaluate_evidence(V2)
        self.assertEqual(result["loss_status"], "needs_review")
        self.assertIsNone(result["net_loss_cents"])
        self.assertEqual(result["total_committed_cents"], 250)
        self.assertIn("obligation_spec_missing", result["unknown_parts"])
        self.assertEqual(result["coverage_status_input"], "needs_review")

    def test_synthetic_spec_verified_zero_and_overpayment(self):
        ok = evaluate_evidence(V1, spec_for(V1, [{"ref": "o1/i1", "template_order_id": "order-1",
                                                  "template_item_id": "item-1", "legally_due_cents": 333}]))
        self.assertEqual((ok["loss_status"], ok["net_loss_cents"]), ("verified", 0))
        over = evaluate_evidence(V1, spec_for(V1, [{"ref": "o1/i2", "template_order_id": "order-1",
                                                    "template_item_id": "item-2", "legally_due_cents": 0}]))
        self.assertEqual(over["net_loss_cents"], 333)
        self.assertTrue(any(o["ref"].startswith("unlisted:") for o in over["obligations"]))

    def test_spec_must_match_case_and_versions(self):
        bad = spec_for(V1, [], policy_version="other-policy")
        with self.assertRaises(SpecError):
            evaluate_evidence(V1, bad)
        with self.assertRaises(ValueError):
            evaluate_evidence(V2, spec_for(V2, [{"ref": "x", "template_order_id": "order-1",
                                                 "template_item_id": "item-1", "legally_due_cents": 0}]))

    def test_legacy_evidence_is_not_mapped_by_guessing(self):
        result = evaluate_evidence(LEGACY)
        self.assertEqual(result["identity"]["case_context_status"], "legacy_unavailable")
        self.assertTrue(all(o["template_item_id"] is None for o in result["obligations"]))
        with self.assertRaises(ValueError):
            evaluate_evidence(LEGACY, spec_for(V1, []))

    def test_tampered_ledger_forces_needs_review(self):
        tampered = deepcopy(V1)
        tampered["ledger"][0]["merchant_delta_cents"] = -300
        result = evaluate_evidence(tampered, spec_for(V1, [{"ref": "o1/i1", "template_order_id": "order-1",
                                                            "template_item_id": "item-1", "legally_due_cents": 333}]))
        self.assertEqual(result["loss_status"], "needs_review")
        self.assertIn("ledger_integrity_issue", result["unknown_parts"])

    def test_schema_file_matches_model(self):
        self.assertEqual(TARGET.read_text(encoding="utf-8"), render())


if __name__ == "__main__":
    unittest.main()
