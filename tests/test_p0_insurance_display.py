"""P0 unit tests; no real Agent run, payment system, or private Gold accessed."""
import unittest
from scripts.p0_insurance_display import _load_contracts, sample_display, evaluate_saved_loss, DEFAULT_CONTRACTS
from scripts.p0_premium_evidence import assess


class P0DisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts = _load_contracts(DEFAULT_CONTRACTS)
        cls.samples = sample_display(cls.contracts)["examples"]

    def test_normal_zero(self):
        normal = self.samples[0]
        self.assertEqual(normal["net_loss_cents"], 0)
        self.assertEqual([x["payout_cents"] for x in normal["claims"]], [0, 0])

    def test_520_yuan_manual_comparison(self):
        result = self.samples[1]
        self.assertEqual(result["source_type"], "engineering_case")
        self.assertEqual(result["net_loss_cents"], 52000)
        self.assertEqual([x["payout_cents"] for x in result["claims"]], [33600, 47000])
        self.assertEqual([x["retained_loss_cents"] for x in result["claims"]], [18400, 5000])
        self.assertTrue(all(x["annual_aggregate_calculation_status"]=="display_only_not_enforced" for x in result["claims"]))

    def test_unknown_stays_null(self):
        result = self.samples[2]
        self.assertTrue(all(x["claim_status"]=="needs_review" and x["payout_cents"] is None for x in result["claims"]))
        self.assertIsNone(result["net_loss_cents"])

    def test_real_C_loss_without_coverage_stays_pending(self):
        c = {"identity":{"episode_id":"e1","case_id":"A1-W_L-01"},
             "obligation_source":"obligation_spec","net_loss_cents":0,
             "loss_status":"verified","coverage_status_input":"needs_review"}
        display = evaluate_saved_loss(c, self.contracts)
        self.assertEqual([x["payout_cents"] for x in display["claims"]], [None, None])
        self.assertEqual([x["claim_status"] for x in display["claims"]], ["needs_review", "needs_review"])

    def test_missing_gold_forces_unknown(self):
        c = {"identity":{"episode_id":"e1","case_id":"A1-W_L-01"},
             "obligation_source":"none", "net_loss_cents":0,
             "loss_status":"verified", "coverage_status_input":"covered"}
        view = evaluate_saved_loss(c, self.contracts)
        self.assertTrue(all(x["payout_cents"] is None for x in view["claims"]))

    def test_annual_cap_never_applied_by_this_script(self):
        for sample in self.samples:
            for c in sample["claims"]:
                self.assertIn("annual_aggregate_limit_cents", c)
                self.assertNotIn("annual_aggregate_paid_cents", c)
                self.assertFalse(c["commercial_quote"])

    def test_premium_is_insufficient(self):
        s = assess({"annual_agent_task_volume":6105, "target_weights":{"whole_low":None,"whole_high":None,"partial_low":None,"partial_high":None}})
        self.assertEqual(s["status"], "insufficient_evidence")
        self.assertIsNone(s["annual_pure_risk_cost_cents"])

    def test_assumption_only_premium_arithmetic(self):
        a = {"annual_agent_task_volume":100, "target_weights":dict.fromkeys(("whole_low","whole_high","partial_low","partial_high"),0.25),
             "estimate_source":"research_assumption", "estimated_payout_cents_per_task_by_product":{
             "AgentShield-Core":dict.fromkeys(("whole_low","whole_high","partial_low","partial_high"),100),
             "AgentShield-Plus":dict.fromkeys(("whole_low","whole_high","partial_low","partial_high"),200)}}
        out = assess(a)
        self.assertEqual(out["status"],"illustrative_assumptions_only")
        self.assertEqual(out["annual_pure_risk_cost_cents"], {"AgentShield-Core":10000,"AgentShield-Plus":20000})
        self.assertIsNone(out["commercial_premium_cents"])


if __name__ == "__main__":
    unittest.main()
