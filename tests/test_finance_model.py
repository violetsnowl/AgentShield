import json
import unittest

from experiments.finance_model import ANNUAL_RESULTS, FOURTH_YEAR, NEW, OLD, budget, market, merchants_for_flat_cash, merchants_to_break_even, price_to_break_even, scenarios

WAN = 10000.0


class OldPlanTests(unittest.TestCase):
    """The plan's printed table, so the new case starts from numbers that are known to match."""

    def setUp(self):
        self.rows = budget(OLD)

    def test_accounts_and_merchants(self):
        self.assertEqual([round(row["accounts"], 2) for row in self.rows], [1.0, 3.3, 6.82])
        self.assertEqual([round(row["merchants"]) for row in self.rows], [50, 165, 341])

    def test_revenue_and_direct_cost(self):
        self.assertEqual([round(row["revenue"] / WAN, 3) for row in self.rows], [60.0, 154.8, 305.52])
        self.assertEqual([round(row["direct_cost"] / WAN, 3) for row in self.rows], [29.6, 68.88, 132.752])

    def test_surplus_and_cash(self):
        self.assertEqual([round(row["surplus"] / WAN, 3) for row in self.rows], [-53.6, -24.08, 22.768])
        self.assertEqual([round(row["closing_cash"] / WAN, 3) for row in self.rows], [99.4, 56.36, 48.984])


class NewPlanTests(unittest.TestCase):
    def test_only_the_stated_fields_changed(self):
        changed = {name for name in OLD.__dataclass_fields__ if getattr(OLD, name) != getattr(NEW, name)}
        self.assertEqual(changed, {"merchants_per_account", "merchant_price", "merchant_cost"})

    def test_break_even_really_is_break_even(self):
        from dataclasses import replace
        needed = merchants_to_break_even(NEW)
        self.assertAlmostEqual(budget(replace(NEW, merchants_per_account=needed))[2]["surplus"], 0.0, places=4)

    def test_monitoring_cost_carries_the_sentinel_model_bill(self):
        stored = json.loads(ANNUAL_RESULTS.read_text(encoding="utf-8"))
        standard = next(row for row in stored["sentinel"] if (row["tasks"], row["threshold"]) == (10, 3))
        self.assertEqual(NEW.merchant_cost, OLD.merchant_cost - 100 + round(standard["model_cost_high"]))

    def test_the_market_is_capped_by_physical_goods_retail(self):
        rows = market()
        self.assertAlmostEqual(rows[0]["merchant_equivalents"], 13.09e12 / (102400661.08 * 100000 / 6105))
        self.assertAlmostEqual(rows[0]["merchants"], rows[0]["merchant_equivalents"] * 0.10)
        self.assertAlmostEqual(rows[1]["monitoring"], rows[1]["merchants"] * 7200.0)

    def test_the_premium_pool_uses_the_monitored_premium(self):
        stored = json.loads(ANNUAL_RESULTS.read_text(encoding="utf-8"))
        watched = next(row["insured"] for row in stored["tiers"] if row["tier"] == "B" and row["monitored"])
        row = market()[0]
        self.assertAlmostEqual(row["premium_low"], row["merchants"] * watched["premium"])
        self.assertAlmostEqual(row["premium_high"], row["merchants"] * watched["premium_with_capital"])

    def test_each_scenario_changes_what_it_says(self):
        rows = {name: values[2] for name, values in scenarios().items()}
        self.assertAlmostEqual(rows["每家厂商 50 家商户"]["surplus"] / WAN, 67.6, places=0)
        self.assertAlmostEqual(rows["续约率 80%"]["surplus"] / WAN, -27.2, places=0)
        self.assertAlmostEqual(rows["新增账户减半，测评联动"]["surplus"] / WAN, -83.3, places=0)
        self.assertAlmostEqual(rows["监测价 4,800 元"]["surplus"] / WAN, -49.3, places=0)
        self.assertAlmostEqual(rows["应收占收入 40%"]["closing_cash"] / WAN, -50.1, places=0)

    def test_the_vendor_pool_follows_from_the_merchant_count(self):
        row = market()[0]
        self.assertAlmostEqual(row["vendors"], row["merchants"] / 20)
        self.assertAlmostEqual(row["vendor_plans"], row["vendors"] * 120000.0)

    def test_the_fourth_year_extends_the_same_budget(self):
        rows = budget(FOURTH_YEAR)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[2]["surplus"], budget(NEW)[2]["surplus"])
        self.assertAlmostEqual(rows[3]["surplus"] / WAN, 31.0, places=0)

    def test_a_lower_monitoring_price_needs_many_more_merchants(self):
        from dataclasses import replace
        self.assertAlmostEqual(merchants_to_break_even(replace(NEW, merchant_price=4800.0)), 62.2, places=0)

    def test_the_other_ways_to_break_even_really_do(self):
        from dataclasses import replace
        self.assertAlmostEqual(budget(replace(NEW, merchant_price=price_to_break_even(NEW, "merchant_price")))[2]["surplus"], 0.0, places=4)
        self.assertAlmostEqual(budget(replace(NEW, account_price=price_to_break_even(NEW, "account_price")))[2]["surplus"], 0.0, places=4)
        flat = budget(replace(NEW, merchants_per_account=merchants_for_flat_cash(NEW)))
        self.assertAlmostEqual(flat[2]["closing_cash"], flat[1]["closing_cash"], places=2)


if __name__ == "__main__":
    unittest.main()
