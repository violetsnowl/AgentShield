"""Cross-check independent handwritten engineering loss cases and insurance formula."""
import json
from pathlib import Path
import unittest
from actuarial.claims import calculate_claim

ROOT = Path(__file__).resolve().parents[1]


class EngineeringCaseTests(unittest.TestCase):
    def test_event_amounts_and_hand_calculated_payouts(self):
        contract = json.loads((ROOT / "configs/insurance/research_contract_v0.1.json").read_text(encoding="utf-8"))
        cases = json.loads((ROOT / "docs/business/engineering_claim_cases_v0.1.json").read_text(encoding="utf-8"))["cases"]
        self.assertGreaterEqual(len(cases), 8)
        for c in cases:
            with self.subTest(case=c["id"]):
                if c["loss_status"] == "verified":
                    computed_extra = sum(max(o["committed_cents"] - o["legally_due_cents"], 0)
                                         for o in c["obligations"])
                    self.assertEqual(computed_extra, c["total_extra_cents"])
                    self.assertLessEqual(c["traceable_recovery_cents"], computed_extra)
                    self.assertEqual(computed_extra - c["traceable_recovery_cents"], c["net_loss_cents"])
                else:
                    self.assertIsNone(c["net_loss_cents"])
                result = calculate_claim({"event_id": c["id"], "net_loss_cents": c["net_loss_cents"],
                                          "loss_status": c["loss_status"], "coverage_status": c["coverage_status"]}, contract)
                self.assertEqual(result["payout_cents"], c["expected_indemnity_cents"])
                self.assertEqual(result["retained_loss_cents"], c["expected_retained_cents"])


if __name__ == "__main__":
    unittest.main()
