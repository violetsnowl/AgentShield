"""Standard-library tests; engineering amounts, NOT real Agent losses."""
import unittest
from actuarial.claims import calculate_claim
from actuarial.contracts import ContractError, ResearchContract

CONTRACT = {"contract_version": "test-v0.1", "currency": "CNY", "deductible_cents": 10000,
            "coinsurance_bp": 10000, "occurrence_limit_cents": 100000, "commercial_quote": False}


def event(amount=0, coverage="covered", loss_status="verified"):
    return {"event_id": "engineering-01", "net_loss_cents": amount,
            "coverage_status": coverage, "loss_status": loss_status}


class ClaimTests(unittest.TestCase):
    def test_contract_from_mapping(self):
        self.assertEqual(ResearchContract.from_mapping(CONTRACT).deductible_cents, 10000)

    def test_ordinary_refund_has_no_incremental_loss(self):
        self.assertEqual(calculate_claim(event(0), CONTRACT)["payout_cents"], 0)

    def test_blocked_attempt_without_committed_transaction(self):
        self.assertEqual(calculate_claim(event(0), CONTRACT)["retained_loss_cents"], 0)

    def test_80_should_be_paid_800_was_paid_200_recovered(self):
        # Extra 720 - recovered 200 = net 520; deductible 100 -> payout 420.
        r = calculate_claim(event(52000), CONTRACT)
        self.assertEqual((r["payout_cents"], r["retained_loss_cents"]), (42000, 10000))

    def test_deductible_once_per_event(self):
        # Verified oracle aggregated two distinct extra payouts into one event.
        self.assertEqual(calculate_claim(event(30000), CONTRACT)["payout_cents"], 20000)

    def test_full_recovery_is_not_a_cash_loss_at_horizon(self):
        self.assertEqual(calculate_claim(event(0), CONTRACT)["payout_cents"], 0)

    def test_not_covered_even_if_economic_loss_is_verified(self):
        r = calculate_claim(event(30000, coverage="excluded"), CONTRACT)
        self.assertEqual((r["claim_status"], r["payout_cents"], r["retained_loss_cents"]),
                         ("not_covered", 0, 30000))

    def test_exact_deductible_and_cap(self):
        self.assertEqual(calculate_claim(event(10000), CONTRACT)["payout_cents"], 0)
        self.assertEqual(calculate_claim(event(999999), CONTRACT)["payout_cents"], 100000)

    def test_half_up_integer_cent(self):
        c = dict(CONTRACT, deductible_cents=0, coinsurance_bp=5000)
        self.assertEqual(calculate_claim(event(1), c)["payout_cents"], 1)
        self.assertEqual(calculate_claim(event(3), c)["payout_cents"], 2)
        c["coinsurance_bp"] = 3333
        self.assertEqual(calculate_claim(event(3), c)["payout_cents"], 1)

    def test_unknown_loss_or_coverage_never_filled_zero(self):
        r = calculate_claim(event(None, loss_status="needs_review"), CONTRACT)
        self.assertIsNone(r["payout_cents"])
        self.assertIsNone(r["net_loss_cents"])
        r = calculate_claim(event(30000, coverage="needs_review"), CONTRACT)
        self.assertEqual(r["claim_status"], "needs_review")
        self.assertIsNone(r["payout_cents"])

    def test_invalid_fields_rejected(self):
        for amount in (-1, True, 1.5, "500"):
            with self.subTest(amount=amount), self.assertRaises(ContractError):
                calculate_claim(event(amount), CONTRACT)
        with self.assertRaises(ContractError):
            calculate_claim(event(None), CONTRACT)
        with self.assertRaises(ContractError):
            calculate_claim(event(3), dict(CONTRACT, deductible_cents=True))
        with self.assertRaises(ContractError):
            calculate_claim(event(3), dict(CONTRACT, coinsurance_bp=10001))
        with self.assertRaises(ContractError):
            calculate_claim(event(3), dict(CONTRACT, commercial_quote=True))
        with self.assertRaises(ContractError):
            calculate_claim(event(3), dict(CONTRACT, occurrence_limit_cents=-1))
        with self.assertRaises(ContractError):
            calculate_claim({"event_id": "missing", "net_loss_cents": 1}, CONTRACT)


if __name__ == "__main__":
    unittest.main()
