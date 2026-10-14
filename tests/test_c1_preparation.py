"""Formal-plan gates, cost projection, and opening-refund attribution. No network and no Gold."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

from evaluator.evidence_adapter import extract_facts, parse_bundle
from evaluator.verify import evaluate_evidence
from experiments.check_opening_refunds import check_payload, opening_counted_as_loss
from experiments.formal_gates import L1_AGENT_RUNS, L1_BASELINE_RUNS, dev_launch_block, formal_blockers
from experiments.prepare_cost_pretrial import load_rows, project
from experiments.rerun_policy import classify_rerun
from experiments.run_dev import main as run_dev_main
from experiments.run_formal import main as run_formal_main

ROOT = Path(__file__).resolve().parents[1]
V1 = json.loads((ROOT / "contracts/evidence_example.json").read_text(encoding="utf-8"))


def add_opening(bundle, cents):
    """Move pre-session money into the initial snapshot without adding an episode refund."""
    updated = deepcopy(bundle)
    initial, final = updated["initial_snapshot"], updated["final_snapshot"]
    for snapshot in (initial, final):
        order, item = snapshot["orders"][0], snapshot["orders"][0]["items"][0]
        order["refunded_cents"] += cents
        item["refunded_cents"] += cents
        snapshot["customer_balance_cents"] += cents
        snapshot["merchant_balance_cents"] -= cents
    return updated


class FormalGateTests(unittest.TestCase):
    def test_committed_plans_cannot_launch(self):
        for name in ("l1_formal_blocked.json", "c1_cost_pretrial_blocked.json"):
            plan = json.loads((ROOT / "experiments/plans" / name).read_text(encoding="utf-8"))
            self.assertIsNotNone(dev_launch_block(plan))
            self.assertNotIn("datasets/gold", json.dumps(plan))
        dev = json.loads((ROOT / "experiments/plans/c1_rule_baseline_dev.json").read_text(encoding="utf-8"))
        self.assertIsNone(dev_launch_block(dev))
        self.assertTrue(dev["runs"])
        self.assertNotIn("scenario", dev["runs"][0])

    def test_formal_runner_stays_closed_even_if_execute_is_requested(self):
        code = run_formal_main(["--plan", "experiments/plans/l1_formal_blocked.json", "--execute"])
        self.assertEqual(code, 2)
        plan = json.loads((ROOT / "experiments/plans/l1_formal_blocked.json").read_text(encoding="utf-8"))
        blockers = formal_blockers(plan, execute=True, env_flag="true")
        self.assertIn("Gold 未冻结", blockers)
        self.assertIn("真实付费预算未确认", blockers)
        self.assertEqual((plan["agent_run_slots"], plan["baseline_run_slots"]), (L1_AGENT_RUNS, L1_BASELINE_RUNS))
        self.assertEqual(plan["independent_business_samples"], 28)
        self.assertEqual(plan["runs"], [])

    def test_dev_runner_exits_before_starting_a_blocked_plan(self):
        argv = sys.argv
        try:
            sys.argv = ["run_dev", "--plan", "experiments/plans/l1_formal_blocked.json"]
            with self.assertRaises(SystemExit) as raised:
                run_dev_main()
            self.assertEqual(raised.exception.code, 2)
        finally:
            sys.argv = argv

    def test_completed_runs_are_not_repeated_to_improve_the_score(self):
        self.assertEqual(classify_rerun("completed", "finish_case_tool")["decision"], "forbidden_cherry_pick")
        recovery = classify_rerun("infra_error", "transport_unknown_after_recovery", purpose="infrastructure_recovery")
        self.assertEqual(recovery["decision"], "infra_rerun_eligible")
        self.assertFalse(recovery["counts_as_new_sample"])
        again = classify_rerun("infra_error", "transport_unknown", already_rerun=True, purpose="infrastructure_recovery")
        self.assertEqual(again["decision"], "record_only")


class CostPretrialTests(unittest.TestCase):
    def test_projection_uses_recorded_upper_bound_and_calls_no_provider(self):
        rows = load_rows(ROOT / "experiments/fixtures/observed_dev_cost_ledger.jsonl")
        estimate = project(rows)
        self.assertEqual(estimate["observed_dev_runs"], 3)
        self.assertAlmostEqual(estimate["observed_cost_cny_upper"], 0.085458)
        self.assertAlmostEqual(estimate["unit_upper_cny"], 0.032044)
        self.assertEqual(estimate["pretrial_remaining_runs"], 7)
        self.assertAlmostEqual(estimate["pretrial_remaining_authorization_cny"], round(7 * 0.032044 * 3, 6))
        self.assertAlmostEqual(estimate["formal_56_authorization_cny"], round(56 * 0.032044 * 3, 6))
        self.assertFalse(estimate["paid_api_called"])
        self.assertFalse(estimate["budget_confirmed"])
        self.assertFalse(estimate["formal_runs_started"])
        self.assertFalse(estimate["pretrial_counts_toward_formal_56"])


class OpeningRefundTests(unittest.TestCase):
    def test_recorded_examples_have_no_opening_refund(self):
        facts = extract_facts(parse_bundle(V1))
        self.assertEqual(facts["opening_refunded_cents"], 0)
        self.assertEqual(facts["total_committed_cents"], 333)
        self.assertEqual(facts["ledger_checks"]["issues"], [])

    def test_opening_balance_is_excluded_from_episode_loss(self):
        opened = add_opening(V1, 200)
        report = check_payload(opened)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["raw"]["opening_refunded_cents"], 200)
        self.assertEqual(report["raw"]["opening_customer_balance_cents"], 200)
        self.assertEqual(report["total_committed_cents"], 333)
        self.assertIsNone(report["net_loss_cents"])
        result = evaluate_evidence(opened)
        self.assertTrue(any("excluded from total_committed_cents" in note for note in result["notes"]))
        self.assertFalse(opening_counted_as_loss(200, 333, result["total_committed_cents"], result["net_loss_cents"]))

    def test_opening_alone_is_not_a_current_loss(self):
        opened = add_opening(V1, 200)
        opened["refunds"] = []
        opened["ledger"] = []
        final = opened["final_snapshot"]
        initial = opened["initial_snapshot"]
        final["orders"] = deepcopy(initial["orders"])
        final["merchant_balance_cents"] = initial["merchant_balance_cents"]
        final["customer_balance_cents"] = initial["customer_balance_cents"]
        result = evaluate_evidence(opened)
        self.assertEqual(result["total_committed_cents"], 0)
        self.assertNotEqual(result["net_loss_cents"], 200)
        facts = extract_facts(parse_bundle(opened))
        self.assertEqual(facts["opening_refunded_cents"], 200)
        self.assertEqual(facts["ledger_checks"]["issues"], [])


if __name__ == "__main__":
    unittest.main()
