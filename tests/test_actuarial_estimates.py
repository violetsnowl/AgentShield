"""B0/B1 engineering checks: repeated cases, weights, holdout and missingness."""
from copy import deepcopy
import unittest
from actuarial.contracts import ContractError
from actuarial.estimate import calculate_quote, STRATA

WEIGHTS = {"whole_low": "0.1", "whole_high": "0.2", "partial_low": "0.3", "partial_high": "0.4"}
KW = dict(config_id="agent-test-v0", contract_version="research-test-v0", data_version="synthetic-v1",
          run_manifest_ref="engineering-only-manifest", target_weights=WEIGHTS, target_volume=1000)


def rec(case_id, stratum, payment, *, split="estimation", run_id=None, parent=None, source="scripted_test"):
    return {"case_id": case_id, "run_id": run_id or f"run-{case_id}-{split}",
            "parent_case_id": parent, "config_id": "agent-test-v0", "stratum": stratum,
            "split": split, "claim_status": "assessed" if payment is not None else "needs_review",
            "payout_cents": payment, "execution_source": source}


def sample():
    return [rec("e1", "whole_low", 100), rec("e1", "whole_low", 300, run_id="run-e1b"),
            rec("e2", "whole_high", 400), rec("e3", "partial_low", 600),
            rec("e4", "partial_high", 800),
            rec("t1", "whole_low", 300, split="holdout"),
            rec("t2", "whole_high", 500, split="holdout"),
            rec("t3", "partial_low", 700, split="holdout"),
            rec("t4", "partial_high", 900, split="holdout")]


class EstimateTests(unittest.TestCase):
    def test_prestratification_repeats_holdout(self):
        r = calculate_quote(sample(), **KW)
        self.assertEqual(r["estimation"]["case_count"], 4)
        self.assertEqual(r["run_count"], 9)
        # case e1 = (100+300)/2=200. Pooled = (200+400+600+800)/4=500.
        self.assertEqual(r["methods"]["B0"]["estimated_mean_cents_decimal"], "500.0000")
        self.assertEqual(r["methods"]["B0"]["scenario_cost_cents_decimal"], "500000.0000")
        # B1 = .1*200+.2*400+.3*600+.4*800 = 600 cents.
        self.assertEqual(r["methods"]["B1"]["estimated_mean_cents_decimal"], "600.0000")
        self.assertEqual(r["methods"]["B1"]["scenario_cost_cents_decimal"], "600000.0000")
        self.assertEqual(r["holdout_evaluation"]["reference_cents_decimal"], "700.0000")
        self.assertEqual(r["holdout_evaluation"]["B0_abs_error_cents_decimal"], "200.0000")
        self.assertEqual(r["holdout_evaluation"]["B1_abs_error_cents_decimal"], "100.0000")
        self.assertFalse(r["commercial_quote"])
        self.assertEqual(r["status"], "illustrative")
        self.assertEqual(r["methods"]["B2"]["status"], "not_fitted")

    def test_stratum_missing_blocks_scenario(self):
        rows = [x for x in sample() if x["stratum"] != "partial_high"]
        r = calculate_quote(rows, **KW)
        self.assertEqual(r["status"], "insufficient_evidence")
        self.assertIsNone(r["methods"]["B1"]["scenario_cost_cents_decimal"])
        self.assertIn("partial_high", r["estimation"]["missing_target_strata"])

    def test_zero_observed_payouts_not_zero_risk_quote(self):
        rows = [rec(f"e{i}", stratum, 0) for i, stratum in enumerate(STRATA)]
        r = calculate_quote(rows, **KW)
        self.assertEqual(r["estimation"]["pooled_mean_cents_decimal"], "0.0000")
        self.assertEqual(r["status"], "insufficient_evidence")
        self.assertIsNone(r["methods"]["B0"]["scenario_cost_cents_decimal"])

    def test_unverified_run_blocks_completion(self):
        rows = sample()
        rows[0] = rec("e1", "whole_low", None)
        r = calculate_quote(rows, **KW)
        self.assertGreater(r["estimation"]["unverified_case_count"], 0)
        self.assertEqual(r["status"], "insufficient_evidence")

    def test_different_weights_change_b1_not_b0(self):
        kw = dict(KW, target_weights={"whole_low": "0.7", "whole_high": "0.1",
                                      "partial_low": "0.1", "partial_high": "0.1"})
        new = calculate_quote(sample(), **kw)
        old = calculate_quote(sample(), **KW)
        self.assertEqual(new["methods"]["B0"], old["methods"]["B0"])
        self.assertNotEqual(new["methods"]["B1"], old["methods"]["B1"])

    def test_invalid_weights_and_volume(self):
        for weights in [dict(WEIGHTS, partial_high="0.5"), dict(WEIGHTS, whole_low="-0.1"),
                        dict(WEIGHTS, whole_low=True), dict(WEIGHTS, partial_high="NaN")]:
            with self.subTest(weights=weights), self.assertRaises(ContractError):
                calculate_quote(sample(), **dict(KW, target_weights=weights))
        with self.assertRaises(ContractError):
            calculate_quote(sample(), **dict(KW, target_volume=True))
        with self.assertRaises(ContractError):
            calculate_quote(sample(), **dict(KW, target_volume=0))

    def test_no_split_leakage(self):
        rows = sample()
        rows[-1]["case_id"] = "e1"
        with self.assertRaises(ContractError):
            calculate_quote(rows, **KW)
        rows = sample()
        rows[-1]["parent_case_id"] = "e1"
        with self.assertRaises(ContractError):
            calculate_quote(rows, **KW)

    def test_duplicate_and_falsified_claim(self):
        rows = sample()
        rows[-1]["run_id"] = rows[0]["run_id"]
        with self.assertRaises(ContractError):
            calculate_quote(rows, **KW)
        rows = sample()
        rows[0]["claim_status"] = "not_covered"
        with self.assertRaises(ContractError):
            calculate_quote(rows, **KW)
        rows = sample()
        rows[0]["payout_cents"] = True
        with self.assertRaises(ContractError):
            calculate_quote(rows, **KW)

    def test_incomplete_holdout_does_not_publish_error_comparison(self):
        rows = sample()
        rows[-1]["claim_status"] = "needs_review"
        rows[-1]["payout_cents"] = None
        result = calculate_quote(rows, **KW)
        self.assertIsNone(result["holdout_evaluation"]["reference_cents_decimal"])
        self.assertIsNone(result["holdout_evaluation"]["B0_abs_error_cents_decimal"])
        self.assertEqual(result["status"], "illustrative")

    def test_sources_not_mixed(self):
        rows = sample()
        rows[0]["execution_source"] = "observed_agent_execution"
        with self.assertRaises(ContractError):
            calculate_quote(rows, **KW)

    def test_empty_records(self):
        r = calculate_quote([], **KW)
        self.assertEqual(r["status"], "insufficient_evidence")
        self.assertIsNone(r["methods"]["B0"]["estimated_mean_cents_decimal"])


if __name__ == "__main__":
    unittest.main()
