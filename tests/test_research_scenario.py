import copy
import json
import unittest

from actuarial.research_scenario import DEFAULT_PRODUCTS, DEFAULT_SCENARIO, calculate_research_scenario, load_research_scenario


class ResearchScenarioTests(unittest.TestCase):
    def test_default_risk_and_reference_premiums(self):
        result = load_research_scenario()
        self.assertEqual(result["annual_agent_task_volume"], 6105)
        self.assertEqual(sum(row["task_count"] for row in result["categories"]), 6105)
        self.assertEqual(result["expected_annual_economic_loss_cents"], 3174600)
        plans = {row["product_id"]: row for row in result["plans"]}
        self.assertEqual(plans["AgentShield-Core"]["scenario_event_payout_cents"]["whole_low"], 33600)
        self.assertEqual(plans["AgentShield-Core"]["annual_reference_premium_cents"], 2564100)
        self.assertEqual(plans["AgentShield-Plus"]["scenario_event_payout_cents"]["whole_low"], 47000)
        self.assertEqual(plans["AgentShield-Plus"]["annual_reference_premium_cents"], 3586688)
        self.assertFalse(result["commercial_quote"])

    def test_changed_shared_assumptions_recalculate_both_outputs(self):
        scenario = json.loads(DEFAULT_SCENARIO.read_text(encoding="utf-8"))
        products = json.loads(DEFAULT_PRODUCTS.read_text(encoding="utf-8"))
        changed = copy.deepcopy(scenario)
        changed["premium_loading_ratio"] = "0.10"
        for row in changed["categories"].values():
            row["accident_probability"] = "0.02"
            row["average_accident_loss_cents"] = 60000
        result = calculate_research_scenario(changed, products)
        self.assertEqual(result["expected_annual_economic_loss_cents"], 7326000)
        plans = {row["product_id"]: row for row in result["plans"]}
        self.assertEqual(plans["AgentShield-Core"]["annual_reference_premium_cents"], 5372400)
        self.assertEqual(plans["AgentShield-Plus"]["annual_reference_premium_cents"], 7387050)

    def test_category_counts_must_match_volume(self):
        scenario = json.loads(DEFAULT_SCENARIO.read_text(encoding="utf-8"))
        products = json.loads(DEFAULT_PRODUCTS.read_text(encoding="utf-8"))
        scenario["categories"]["whole_low"]["task_count"] -= 1
        with self.assertRaisesRegex(ValueError, "task counts"):
            calculate_research_scenario(scenario, products)


if __name__ == "__main__":
    unittest.main()
