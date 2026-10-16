"""Fixed-case agent preparation stays blocked and does not special-case one fixture."""
import json
from pathlib import Path
import unittest

from experiments.fixed_cases import P_H_03_MARK, local_allowlist_gap, readiness
from experiments.formal_gates import dev_launch_block
from experiments.reverify_evidence import reverify
from runners.env import paid_authorization

ROOT = Path(__file__).resolve().parents[1]


class FixedCasePrepTests(unittest.TestCase):
    def test_readiness_stays_closed_on_this_checkout(self):
        report = readiness()
        self.assertFalse(report["ready_to_launch"])
        self.assertFalse(report["paid_api_called"])
        self.assertEqual(report["a1_p_h_03"]["classification"], P_H_03_MARK)
        self.assertEqual(report["a1_p_h_03"]["business_judgment"], "pending_A")
        self.assertEqual(local_allowlist_gap(), ["A1-W_L-01", "A1-P_H-03", "A1-P_L-05", "ENG-A0-06"])
        self.assertTrue(any("fixture 枚举" in item for item in report["blockers"]))

    def test_dev_runner_refuses_the_fixed_case_plan(self):
        plan = json.loads((ROOT / "experiments/plans/fixed_cases_agent_dev_blocked.json").read_text(encoding="utf-8"))
        self.assertIsNotNone(dev_launch_block(plan))
        self.assertEqual(len(plan["runs"]), 4)
        self.assertFalse(plan["counts_as_formal_run"])
        self.assertEqual(plan["baseline_wire"]["execution_source"], "scripted_test")
        self.assertNotIn("datasets/gold", json.dumps(plan))

    def test_first_case_plan_waits_on_the_paid_gate(self):
        plan = json.loads((ROOT / "experiments/plans/a1_w_l_01_agent_dev.json").read_text(encoding="utf-8"))
        self.assertIsNone(dev_launch_block(plan))
        self.assertEqual([run["fixture_id"] for run in plan["runs"]], ["A1-W_L-01"])
        self.assertFalse(plan["counts_as_formal_run"])
        self.assertIsNone(plan["obligation_spec"])
        allowed, _, reason = paid_authorization({})
        self.assertFalse(allowed)
        self.assertIn("C_ENABLE_PAID_RUNS", reason)

    def test_saved_evidence_can_be_reverified_without_a_new_model_call(self):
        evidence = json.loads((ROOT / "contracts/evidence_example.json").read_text(encoding="utf-8"))
        contract = json.loads((ROOT / "configs/insurance/research_contract_v0.1.json").read_text(encoding="utf-8"))
        context = evidence["case_context"]
        spec = {"spec_version": "obligation-spec-0.1-candidate", "spec_id": "synthetic-a1-shape",
                "case_id": context["case_id"], "fixture_id": context["fixture_id"],
                "fixture_version": context["fixture_version"], "policy_version": context["policy_version"],
                "source": "synthetic_test_only", "review_status": "not_reviewed", "closed_world": True,
                "obligations": [{"ref": "o1/i1", "template_order_id": "order-1", "template_item_id": "item-1",
                                 "legally_due_cents": 333}],
                "recovery": {"policy": "none_in_sandbox"}, "coverage_status_input": "covered",
                "allowed_outcomes": [], "horizon": "test"}
        loss, claim = reverify(evidence, spec, contract)
        self.assertEqual(loss["net_loss_cents"], 0)
        self.assertIn("claim_status", claim)
        self.assertIn("payout_cents", claim)
        pending, _ = reverify(evidence, None, contract)
        self.assertEqual(pending["loss_status"], "needs_review")
        self.assertIsNone(pending["net_loss_cents"])

    def test_baseline_has_no_case_specific_refund(self):
        text = (ROOT / "runners/baseline.py").read_text(encoding="utf-8")
        self.assertNotIn("A1-P_H-03", text)
        self.assertNotIn("order-main", text)


if __name__ == "__main__":
    unittest.main()
