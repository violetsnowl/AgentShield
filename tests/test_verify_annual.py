from math import sqrt
import unittest

from actuarial.annual import simulate_years
from experiments import annual_report, verify_annual
from experiments.annual_report import Scenario, batch_events, model_for, pricing_frequency, severity_points

try:
    import numpy
except ImportError:
    numpy = None


class StandardLibraryCheckTests(unittest.TestCase):
    def test_sampled_mean_matches_engine_for_tier_b_without_monitoring(self):
        evidence, assumptions = annual_report.load_inputs()
        scene = Scenario.from_assumptions(assumptions)
        tier = evidence["tiers"]["B"]
        model, lam = model_for(evidence, tier, scene, False)
        events = batch_events(evidence, tier, scene, False, pricing_frequency(tier, scene.gate_leak))
        years = 20000
        totals = [sum(ordinary) + sum(batch) for ordinary, batch in simulate_years(years, 20261108, lam, severity_points(evidence), events)]
        mean = sum(totals) / years
        spread = sqrt(sum((total - mean) ** 2 for total in totals) / (years - 1) / years)
        self.assertLess(abs(model.uninsured()["mean"] - mean), 4 * spread)


@unittest.skipUnless(numpy is not None, "numpy is not installed")
class NumpyCheckTests(unittest.TestCase):
    def test_reduced_run_matches_engine_uninsured_mean(self):
        evidence, assumptions = annual_report.load_inputs()
        seed = numpy.random.SeedSequence(20261108)
        cell = verify_annual.check_cell(evidence, assumptions, "B", False, {}, 200000, 20, seed, fine_step=None)
        mean = next(entry for entry in cell["items"] if entry["metric"] == "不投保均值")
        self.assertGreater(mean["se"], 0)
        self.assertLess(abs(mean["z"]), 4)

    def test_tail_definition_splits_the_99_percent_point(self):
        values = numpy.array([1.0] * 98 + [5.0, 9.0])
        p99, cte99 = verify_annual.p99_cte99(values)
        self.assertEqual(p99, 5.0)
        self.assertEqual(cte99, 9.0)
        values = numpy.array([1.0] * 197 + [5.0, 5.0, 9.0])
        p99, cte99 = verify_annual.p99_cte99(values)
        self.assertEqual(p99, 5.0)
        self.assertAlmostEqual(cte99, (9.0 + 5.0) / 2)
        p99, cte99 = verify_annual.p99_cte99(numpy.array([1.0] * 147 + [5.0, 6.0, 9.0]))
        self.assertEqual(p99, 6.0)
        self.assertAlmostEqual(cte99, (9.0 + 0.5 * 6.0) / 1.5)


if __name__ == "__main__":
    unittest.main()
