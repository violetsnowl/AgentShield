import math
import random
import unittest

from actuarial.annual import (AggregateTerms, AnnualContract, AnnualLossModel, PerEventTerms, PremiumBasis, add_atoms, annual_ledger,
                              compound_poisson, discretize, evaluate_sampled, simulate_years, tail_stats)
from actuarial.contracts import ContractError

CONTRACT = {"contract_version": "test-aad", "currency": "CNY", "annual_aggregate_deductible_cents": 8000000,
            "coinsurance_bp": 9000, "annual_limit_cents": 30000000, "commercial_quote": False}
# The four-tier distribution and the common event from the review's exact enumeration.
TIERS = [(200.0, 0.75), (1000.0, 0.20), (5000.0, 0.045), (20000.0, 0.005)]
COMMON = [[(0.02, 150000.0)]]
REVIEW_HANDLING = 80.0 * (100 * 0.25 + 0.02)
REVIEW_SERVICE_FEE = 7200.0


def event(event_id, day, cents, loss="verified", coverage="covered"):
    return {"event_id": event_id, "occurred_at": f"2026-{day}", "net_loss_cents": cents, "loss_status": loss, "coverage_status": coverage}


class LedgerTests(unittest.TestCase):
    def test_a_year_adds_up_exactly_to_the_aggregate_formula(self):
        rng = random.Random(7)
        contract = AnnualContract.from_mapping(CONTRACT)
        for _ in range(200):
            events = [event(f"e{i}", f"{rng.randint(1, 12):02d}-{i:03d}", rng.randint(1, 9000000)) for i in range(rng.randint(0, 30))]
            ledger = annual_ledger(events, contract)
            self.assertEqual(ledger["paid_cents"], contract.paid_to_date(sum(row["net_loss_cents"] for row in events)))
            self.assertEqual(sum(row["payout_cents"] for row in ledger["events"]), ledger["paid_cents"])

    def test_the_order_of_events_does_not_change_the_year(self):
        rng = random.Random(11)
        amounts = [rng.randint(100, 6000000) for _ in range(12)]
        totals = set()
        for _ in range(20):
            rng.shuffle(amounts)
            totals.add(annual_ledger([event(f"e{i}", f"01-{i:02d}", amount) for i, amount in enumerate(amounts)], CONTRACT)["paid_cents"])
        self.assertEqual(len(totals), 1)

    def test_payout_starts_only_after_the_deductible_is_used_up(self):
        ledger = annual_ledger([event("a", "01-01", 7000000), event("b", "02-01", 2000000), event("c", "03-01", 1000000)], CONTRACT)
        self.assertEqual([row["payout_cents"] for row in ledger["events"]], [0, 900000, 900000])
        self.assertEqual([row["deductible_remaining_cents"] for row in ledger["events"]], [1000000, 0, 0])
        self.assertEqual([row["retained_loss_cents"] for row in ledger["events"]], [7000000, 1100000, 100000])

    def test_the_annual_limit_stops_payment(self):
        ledger = annual_ledger([event("a", "01-01", 100000000), event("b", "02-01", 100000)], CONTRACT)
        self.assertEqual([row["payout_cents"] for row in ledger["events"]], [30000000, 0])

    def test_an_excluded_event_does_not_use_the_deductible(self):
        ledger = annual_ledger([event("a", "01-01", 9000000, coverage="excluded"), event("b", "02-01", 9000000)], CONTRACT)
        self.assertEqual(ledger["events"][0]["claim_status"], "not_covered")
        self.assertEqual(ledger["events"][0]["retained_loss_cents"], 9000000)
        self.assertEqual(ledger["covered_loss_cents"], 9000000)
        self.assertEqual(ledger["paid_cents"], 900000)

    def test_an_unknown_amount_stays_null_and_later_events_wait(self):
        ledger = annual_ledger([event("a", "01-01", 9000000), event("b", "02-01", None, loss="needs_review"), event("c", "03-01", 500000)], CONTRACT)
        self.assertEqual(ledger["events"][0]["payout_cents"], 900000)
        self.assertIsNone(ledger["events"][1]["payout_cents"])
        self.assertEqual(ledger["events"][2]["claim_status"], "held_for_prior_event")
        self.assertIsNone(ledger["events"][2]["payout_cents"])
        self.assertFalse(ledger["complete"])

    def test_bad_input_is_refused(self):
        with self.assertRaises(ContractError):
            annual_ledger([event("a", "01-01", None)], CONTRACT)
        with self.assertRaises(ContractError):
            annual_ledger([event("a", "01-01", 5, loss="needs_review")], CONTRACT)
        with self.assertRaises(ContractError):
            annual_ledger([event("a", "01-01", 5), event("a", "01-02", 5)], CONTRACT)
        with self.assertRaises(ContractError):
            AnnualContract.from_mapping({**CONTRACT, "commercial_quote": True})
        with self.assertRaises(ContractError):
            AnnualContract.from_mapping({**CONTRACT, "annual_limit_cents": 0})


class DistributionTests(unittest.TestCase):
    def test_discretizing_keeps_the_mean(self):
        grid = discretize([(123.0, 1.0), (4567.5, 2.0), (50.0, 1.0)], 50.0)
        self.assertAlmostEqual(sum(grid.values()), 1.0)
        self.assertAlmostEqual(sum(index * 50.0 * chance for index, chance in grid.items()), (123 + 2 * 4567.5 + 50) / 4)

    def test_panjer_matches_a_plain_poisson_when_every_loss_is_one_step(self):
        out = compound_poisson(3.0, {1: 1.0}, 40)
        for k in range(12):
            self.assertAlmostEqual(out[k], math.exp(-3.0) * 3.0 ** k / math.factorial(k))

    def test_panjer_keeps_its_mean_and_variance(self):
        grid = {1: 0.5, 4: 0.5}
        out = compound_poisson(20.0, grid, 400)
        mean = sum(k * p for k, p in enumerate(out))
        variance = sum((k - mean) ** 2 * p for k, p in enumerate(out))
        self.assertAlmostEqual(sum(out), 1.0, places=9)
        self.assertAlmostEqual(mean, 20.0 * 2.5, places=6)
        self.assertAlmostEqual(variance, 20.0 * 8.5, places=5)

    def test_a_year_with_thousands_of_events_does_not_underflow(self):
        model = AnnualLossModel(2000.0, [(500.0, 1.0), (1500.0, 1.0)], step=100.0)
        self.assertAlmostEqual(sum(model.density), 1.0, places=8)
        self.assertAlmostEqual(model.uninsured()["mean"], 2000.0 * 1000.0, delta=1.0)

    def test_batch_atoms_shift_the_right_amount_of_mass(self):
        out = add_atoms([1.0], [(0.2, 3)])
        self.assertEqual(len(out), 4)
        self.assertAlmostEqual(out[0], 0.8)
        self.assertAlmostEqual(out[3], 0.2)

    def test_tail_stats_splits_the_atom_at_the_ninety_ninth_percentile(self):
        stats = tail_stats([(0.0, 0.985), (100.0, 0.01), (200.0, 0.005)])
        self.assertEqual(stats["p99"], 100.0)
        self.assertAlmostEqual(stats["cte99"], (100.0 * 0.005 + 200.0 * 0.005) / 0.01)


class ReviewReproductionTests(unittest.TestCase):
    """Section 6 item 1: the review's enumeration in exact.json, to within one yuan."""

    @classmethod
    def setUpClass(cls):
        cls.model = AnnualLossModel(100.0, TIERS, COMMON, step=200.0, tail_sds=30.0)

    def test_no_insurance(self):
        stats = self.model.uninsured()
        self.assertAlmostEqual(stats["mean"], 70500.0, delta=1.0)
        self.assertAlmostEqual(stats["p95"], 107000.0, delta=1.0)
        self.assertAlmostEqual(stats["p99"], 215200.0, delta=1.0)
        self.assertAlmostEqual(stats["cte99"], 231882.31, delta=1.0)

    def test_aggregate_deductible_of_eighty_thousand(self):
        row = self.model.evaluate(AggregateTerms(80000.0, 0.9, 300000.0), PremiumBasis(), handling=REVIEW_HANDLING, service_fee=REVIEW_SERVICE_FEE)
        self.assertAlmostEqual(row["premium"], 20597.96, delta=1.0)
        self.assertAlmostEqual(row["expected_paid"], 5230.64, delta=1.0)
        self.assertAlmostEqual(row["mean"], 85867.32, delta=1.0)
        self.assertAlmostEqual(row["p99"], 114117.96, delta=1.0)
        self.assertAlmostEqual(row["cte99"], 115786.19, delta=1.0)

    def test_aggregate_deductible_of_one_hundred_thousand(self):
        row = self.model.evaluate(AggregateTerms(100000.0, 0.9, 300000.0), PremiumBasis(), handling=REVIEW_HANDLING, service_fee=REVIEW_SERVICE_FEE)
        self.assertAlmostEqual(row["premium"], 16755.16, delta=1.0)
        self.assertAlmostEqual(row["p99"], 128275.16, delta=1.0)
        self.assertAlmostEqual(row["cte99"], 129943.39, delta=1.0)

    def test_core_and_plus_by_sampling_match_the_review(self):
        years = simulate_years(30000, 5, 100.0, TIERS, COMMON)
        expected = {"core": (PerEventTerms(500, 0.8, 20000, 150000, 300000), 34392.0), "plus": (PerEventTerms(200, 0.9, 50000, 300000, 600000), 45446.4)}
        for terms, reference in expected.values():
            row = evaluate_sampled(years, terms, PremiumBasis(), handling=REVIEW_HANDLING, service_fee=REVIEW_SERVICE_FEE)
            self.assertAlmostEqual(row["expected_paid"], reference, delta=reference * 0.02)


class SamplingAgreementTests(unittest.TestCase):
    def test_recursion_and_sampling_agree_within_three_standard_errors(self):
        severity = [(35.0, 1.0), (320.0, 2.0), (900.0, 1.0), (4300.0, 0.2)]
        batch = [[(0.08, 240000.0), (0.02, 60000.0)], [(0.1, 40000.0)]]
        model = AnnualLossModel(90.0, severity, batch, step=25.0)
        terms = AggregateTerms(80000.0, 0.9, 300000.0)
        exact_paid = tail_stats([(terms.paid(loss), mass) for loss, mass in model.outcomes()])["mean"]
        years = simulate_years(40000, 21, 90.0, severity, batch)
        totals = [sum(a) + sum(b) for a, b in years]
        mean = sum(totals) / len(totals)
        sd = math.sqrt(sum((x - mean) ** 2 for x in totals) / (len(totals) - 1))
        self.assertLess(abs(mean - model.uninsured()["mean"]), 3 * sd / math.sqrt(len(totals)))
        paid = [terms.paid(x) for x in totals]
        paid_mean = sum(paid) / len(paid)
        paid_sd = math.sqrt(sum((x - paid_mean) ** 2 for x in paid) / (len(paid) - 1))
        self.assertLess(abs(paid_mean - exact_paid), 3 * paid_sd / math.sqrt(len(paid)))


class PremiumTests(unittest.TestCase):
    def test_the_service_fee_is_a_separate_input(self):
        basis = PremiumBasis()
        self.assertAlmostEqual(basis.premium(1000.0, 0.0), (1200.0 + 1000.0) / 0.8)
        self.assertAlmostEqual(basis.premium(1000.0, 0.0, 7200.0) - basis.premium(1000.0, 0.0), 9000.0)

    def test_capital_loading_replaces_the_flat_loading_only_when_larger(self):
        basis = PremiumBasis()
        self.assertAlmostEqual(basis.premium_with_capital(1000.0, 1100.0, 0.0), basis.premium(1000.0, 0.0))
        self.assertAlmostEqual(basis.premium_with_capital(1000.0, 101000.0, 0.0), (1000.0 + 8000.0 + 1000.0) / 0.8)

    def test_handling_follows_the_years_with_a_claim(self):
        # Almost only the batch event pushes this year past the deductible, and it comes regardless of the count, so a claim
        # year has about the average 10 ordinary events plus the batch event.
        model = AnnualLossModel(10.0, [(1000.0, 1.0)], [[(0.1, 50000.0)]], step=50.0)
        row = model.evaluate(AggregateTerms(30000.0, 0.9, 300000.0), PremiumBasis())
        self.assertAlmostEqual(row["handling"], 80.0 * row["trigger_chance"] * 11.0, delta=1e-3)

    def test_claim_year_cases_match_a_full_enumeration(self):
        lam, severity, batch, deductible = 1.3, [(100.0, 0.6), (300.0, 0.4)], [(0.2, 500.0)], 400.0
        model = AnnualLossModel(lam, severity, [batch], step=50.0)
        sums = {0: 1.0}
        exact = 0.0
        for n in range(60):
            chance_n = math.exp(-lam) * lam ** n / math.factorial(n)
            for occurs, b_chance, b_steps in ((0, 0.8, 0), (1, 0.2, 10)):
                for steps, mass in sums.items():
                    total = steps + b_steps
                    weight = 1.0 if total > 8 else 0.5 if total == 8 else 0.0
                    exact += chance_n * b_chance * mass * weight * (n + occurs)
            grown = {}
            for steps, mass in sums.items():
                for amount, share in severity:
                    grown[steps + int(amount / 50)] = grown.get(steps + int(amount / 50), 0.0) + mass * share
            sums = grown
        self.assertAlmostEqual(model.claim_year_cases(deductible), exact, places=9)
        row = model.evaluate(AggregateTerms(deductible, 0.9, 10000.0), PremiumBasis())
        self.assertAlmostEqual(row["handling"], 80.0 * exact, places=6)

    def test_two_batch_events_below_the_deductible_are_weighed_on_the_other_losses(self):
        # Each batch event alone stays under the deductible, so whether a year claims depends on the other batch event and the
        # ordinary losses. Using the full distribution for a batch event, or leaving the other batch event out, fails here.
        lam, severity, deductible = 0.9, [(100.0, 0.5), (200.0, 0.5)], 400.0
        batch = [[(0.3, 300.0)], [(0.25, 150.0), (0.15, 250.0)]]
        model = AnnualLossModel(lam, severity, batch, step=50.0)
        sums = {0: 1.0}
        outcomes = [((0, 0), 0.7 * 0.6), ((6, 1), 0.3 * 0.6), ((3, 1), 0.7 * 0.25), ((5, 1), 0.7 * 0.15), ((9, 2), 0.3 * 0.25), ((11, 2), 0.3 * 0.15)]
        exact = 0.0
        for n in range(60):
            chance_n = math.exp(-lam) * lam ** n / math.factorial(n)
            for (b_steps, events), b_chance in outcomes:
                for steps, mass in sums.items():
                    total = steps + b_steps
                    weight = 1.0 if total > 8 else 0.5 if total == 8 else 0.0
                    exact += chance_n * b_chance * mass * weight * (n + events)
            grown = {}
            for steps, mass in sums.items():
                for amount, share in severity:
                    grown[steps + int(amount / 50)] = grown.get(steps + int(amount / 50), 0.0) + mass * share
            sums = grown
        self.assertAlmostEqual(model.claim_year_cases(deductible), exact, places=9)

    def test_claim_years_carry_more_events_than_an_average_year(self):
        # Without batch events, a year claims only when it has many events, so the old shortcut lam * P(claim) undercounts.
        model = AnnualLossModel(20.0, [(1000.0, 1.0)], step=50.0)
        row = model.evaluate(AggregateTerms(25000.0, 0.9, 300000.0), PremiumBasis())
        self.assertGreater(row["handling"], 80.0 * row["trigger_chance"] * 20.0 * 1.2)

    def test_mass_on_the_deductible_counts_as_half_a_claim(self):
        model = AnnualLossModel(0.0, [(100.0, 1.0)], [[(0.4, 1000.0)]], step=50.0)
        row = model.evaluate(AggregateTerms(1000.0, 0.9, 300000.0), PremiumBasis())
        self.assertAlmostEqual(row["trigger_chance"], 0.2)

    def test_a_contract_that_never_pays_has_no_claims_cost(self):
        model = AnnualLossModel(1.0, [(100.0, 1.0)], step=50.0)
        row = model.evaluate(AggregateTerms(10000000.0, 0.9, 300000.0), PremiumBasis())
        self.assertAlmostEqual(row["expected_paid"], 0.0)
        self.assertAlmostEqual(row["premium"], 1000.0 / 0.8)
        self.assertAlmostEqual(row["trigger_chance"], 0.0)


if __name__ == "__main__":
    unittest.main()
