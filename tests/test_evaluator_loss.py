"""C oracle against A's hand-calculated engineering cases, then through A's claim function."""
import json
from pathlib import Path
import unittest

from actuarial.claims import calculate_claim
from evaluator.loss import LossInputError, compute_loss
from evaluator.verify import claim_event, evaluate_engineering_case

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "docs/business/engineering_claim_cases_v0.1.json").read_text(encoding="utf-8"))["cases"]
CONTRACT = json.loads((ROOT / "configs/insurance/research_contract_v0.1.json").read_text(encoding="utf-8"))


class EngineeringCaseTests(unittest.TestCase):
    def test_all_nine_cases_match_hand_calculation(self):
        self.assertEqual(len(CASES), 9)
        for case in CASES:
            with self.subTest(case=case["id"]):
                result = evaluate_engineering_case(case)
                self.assertEqual(result["total_extra_cents"], case["total_extra_cents"])
                self.assertEqual(result["traceable_recovery_cents"], case["traceable_recovery_cents"])
                self.assertEqual(result["net_loss_cents"], case["net_loss_cents"])
                self.assertEqual(result["loss_status"], case["loss_status"])
                for got, expected in zip(result["obligations"], case["obligations"]):
                    self.assertEqual(got["extra_cents"], expected["extra_cents"])

    def test_oracle_output_feeds_A_claim_function(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                claim = calculate_claim(claim_event(evaluate_engineering_case(case)), CONTRACT)
                self.assertEqual(claim["payout_cents"], case["expected_indemnity_cents"])
                self.assertEqual(claim["retained_loss_cents"], case["expected_retained_cents"])
                self.assertFalse(claim["commercial_quote"])

    def test_E03_net_520_yuan_indemnity_420_yuan(self):
        case = next(c for c in CASES if c["id"] == "E03_overpay_recover")
        result = evaluate_engineering_case(case)
        claim = calculate_claim(claim_event(result), CONTRACT)
        self.assertEqual((result["net_loss_cents"], claim["payout_cents"]), (52000, 42000))


class PureFunctionTests(unittest.TestCase):
    def test_underpayment_never_offsets_overpayment(self):
        result = compute_loss([{"ref": "a", "legally_due_cents": 10000, "committed_cents": 5000},
                               {"ref": "b", "legally_due_cents": 0, "committed_cents": 5000}], 0)
        self.assertEqual((result["total_extra_cents"], result["total_underpaid_cents"]), (5000, 5000))

    def test_unknown_due_with_outflow_stays_unknown(self):
        result = compute_loss([{"ref": "a", "legally_due_cents": None, "committed_cents": 100}], 0)
        self.assertIsNone(result["total_extra_cents"])
        self.assertIsNone(result["net_loss_cents"])
        self.assertEqual(result["loss_status"], "needs_review")

    def test_no_outflow_means_zero_extra_even_if_due_unknown(self):
        result = compute_loss([{"ref": "a", "legally_due_cents": None, "committed_cents": 0}], 0)
        self.assertEqual(result["total_extra_cents"], 0)
        self.assertIsNone(result["total_underpaid_cents"])

    def test_unknown_recovery_blocks_net_loss(self):
        result = compute_loss([{"ref": "a", "legally_due_cents": 0, "committed_cents": 100}], None)
        self.assertEqual(result["total_extra_cents"], 100)
        self.assertIsNone(result["net_loss_cents"])

    def test_invalid_inputs_rejected(self):
        for bad in (-1, 1.5, True, "100"):
            with self.subTest(bad=bad), self.assertRaises(LossInputError):
                compute_loss([{"ref": "a", "legally_due_cents": 0, "committed_cents": bad}], 0)
        with self.assertRaises(LossInputError):
            compute_loss([{"ref": "a", "legally_due_cents": 0, "committed_cents": 100}], 101)
        with self.assertRaises(LossInputError):
            compute_loss([{"ref": "a", "legally_due_cents": 0, "committed_cents": 1},
                          {"ref": "a", "legally_due_cents": 0, "committed_cents": 1}], 0)


if __name__ == "__main__":
    unittest.main()
