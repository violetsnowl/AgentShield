import json
import math
from pathlib import Path
import secrets
import unittest

from fastapi.testclient import TestClient
import httpx

from actuarial.annual import AnnualContract, simulate_years
from actuarial.annual_summary import load_annual_summary
from experiments import annual_calibration, annual_report
from actuarial.annual import tail_stats
from experiments.annual_report import ATOMS, REFERENCE_TIER, TARGET_CUT, TIE_YUAN, Scenario, batch_events, hours_across, likely_frequency, model_for, pricing_frequency, severity_points, terms_of
from workbench.app import create_observer

CONTRACT_FILE = annual_report.ROOT / "configs/insurance/research_contract_annual_v0.3.json"
ENHANCED_FILE = annual_report.ROOT / "configs/insurance/research_contract_annual_enhanced_v0.3.json"


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stored, cls.assumptions = annual_report.load_inputs()

    def test_the_stored_file_is_what_the_batches_give_today(self):
        self.assertEqual(annual_calibration.build(), self.stored)

    def test_voided_pilots_stay_out(self):
        self.assertEqual(self.stored["real_runs"], 4326)
        self.assertEqual(self.stored["severity"]["accidents"], 162)
        self.assertEqual(self.stored["severity"]["net_loss_cents"], 8601926)

    def test_repeat_runs_of_a_task_count_once_for_severity(self):
        severity = self.stored["severity"]
        self.assertEqual(severity["distinct_tasks"], 69)
        self.assertEqual(len(severity["task_mean_cents"]), 69)

    def test_tiers_use_the_paired_tasks_and_are_not_pooled(self):
        tiers = self.stored["tiers"]
        self.assertEqual([(tiers[key]["evidence"]["accidents"], tiers[key]["evidence"]["runs"]) for key in "ABCD"], [(0, 210), (1, 210), (0, 210), (45, 210)])
        self.assertEqual({tiers[key]["evidence"]["thinking"] for key in "AB"}, {"低思考"})
        self.assertEqual({tiers[key]["evidence"]["thinking"] for key in "CD"}, {"关思考"})

    def test_probes_are_scripted_and_stay_apart_from_model_runs(self):
        probes = self.stored["probes"]
        self.assertEqual({key: probes[key]["tasks"] for key in ("P0", "P1", "P2")}, {"P0": 340, "P1": 340, "P2": 340})
        self.assertEqual(probes["P0"]["accidents"], 305)
        self.assertEqual(probes["P2"]["net_loss_cents"], 0)

    def test_natural_flow_comes_from_every_task_in_the_population(self):
        flow = self.stored["natural_flow"]
        self.assertEqual(flow["tasks"], 6105)
        self.assertEqual(flow["whole_order_per_task_cents"], 47239)
        self.assertEqual(flow["duplicate_per_task_cents"], 80536)
        self.assertEqual(flow["whole_order_share"], 0.5091)

    def test_the_sentinel_rates_are_the_same_route_pair(self):
        sentinel = self.stored["sentinel"]
        self.assertEqual((sentinel["off"]["accidents"], sentinel["low"]["accidents"]), (43, 1))
        self.assertEqual(sentinel["off"]["model"], sentinel["low"]["model"])


class RatingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence, cls.assumptions = annual_report.load_inputs()
        cls.scene = Scenario.from_assumptions(cls.assumptions)

    def test_a_gate_gets_no_credit_for_its_structural_zero_alone(self):
        tiers = self.evidence["tiers"]
        self.assertAlmostEqual(pricing_frequency(tiers["A"], 0.2), tiers["A"]["evidence"]["wilson_high"])
        self.assertAlmostEqual(pricing_frequency(tiers["C"], 0.2), 0.2 * tiers["C"]["open_reference"]["wilson_high"])
        self.assertGreater(pricing_frequency(tiers["C"], 0.2), pricing_frequency(tiers["A"], 0.2))

    def test_zero_accidents_never_price_at_zero(self):
        self.assertGreater(pricing_frequency(self.evidence["tiers"]["A"], 0.0), 0.0)

    def test_configuration_already_off_has_no_extra_drift_event(self):
        tiers = self.evidence["tiers"]
        self.assertEqual(len(batch_events(self.evidence, tiers["B"], self.scene, False)), 2)
        self.assertEqual(len(batch_events(self.evidence, tiers["D"], self.scene, False)), 1)

    def test_a_gate_scales_batch_loss_by_the_leak(self):
        tiers = self.evidence["tiers"]
        open_loss = batch_events(self.evidence, tiers["B"], self.scene, False)[0][0][1]
        gated_loss = batch_events(self.evidence, tiers["A"], self.scene, False)[0][0][1]
        self.assertAlmostEqual(gated_loss, open_loss * self.scene.gate_leak)

    def test_a_fault_lasts_part_of_the_check_cycle(self):
        self.assertEqual(hours_across(24.0), [3.0, 9.0, 15.0, 21.0])
        self.assertEqual(hours_across(4.0, 0.5), [1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(sum(hours_across(24.0)) / ATOMS, 12.0)

    def test_monitoring_splits_the_chance_and_shortens_most_events(self):
        tier = self.evidence["tiers"]["B"]
        plain = batch_events(self.evidence, tier, self.scene, False)[0]
        watched = batch_events(self.evidence, tier, self.scene, True)[0]
        self.assertAlmostEqual(sum(chance for chance, _ in watched), sum(chance for chance, _ in plain))
        self.assertAlmostEqual(sum(chance for chance, _ in watched[:ATOMS]), self.scene.loud_chance * self.scene.catch_share)
        self.assertAlmostEqual(watched[ATOMS - 1][1] / plain[-1][1], 4.0 / 21.0)
        self.assertAlmostEqual(watched[-1][1], plain[-1][1])

    def test_a_loud_fault_is_priced_on_ordinary_requests(self):
        worst = batch_events(self.evidence, self.evidence["tiers"]["B"], self.scene, False)[0][-1][1]
        self.assertAlmostEqual(worst, 100000 / 8760 * 21 * 472.39, delta=1.0)

    def test_drift_only_adds_the_gap_above_the_ordinary_rate(self):
        tier = self.evidence["tiers"]["B"]
        worst = batch_events(self.evidence, tier, self.scene, False)[1][-1][1]
        gap = 45 / 210 - pricing_frequency(tier, self.scene.gate_leak)
        self.assertAlmostEqual(worst, 100000 / 8760 * 630 * 0.05 * gap * 547.85, delta=1.0)

    def test_a_gate_compares_its_leaked_drift_with_its_own_rate(self):
        tier = self.evidence["tiers"]["A"]
        worst = batch_events(self.evidence, tier, self.scene, False)[1][-1][1]
        gap = 45 / 210 * self.scene.gate_leak - pricing_frequency(tier, self.scene.gate_leak)
        self.assertAlmostEqual(worst, 100000 / 8760 * 630 * 0.05 * gap * 547.85, delta=1.0)

    def test_the_likely_rate_sits_under_the_pricing_bound(self):
        tier = self.evidence["tiers"]["B"]
        self.assertAlmostEqual(likely_frequency(tier, 0.2), 1.5 / 211)
        self.assertLess(likely_frequency(tier, 0.2), pricing_frequency(tier, 0.2))

    def test_recursion_and_sampling_agree_on_the_reference_tier(self):
        tier = self.evidence["tiers"][REFERENCE_TIER]
        model, lam = model_for(self.evidence, tier, self.scene, False)
        years = simulate_years(15000, 3, lam, severity_points(self.evidence), batch_events(self.evidence, tier, self.scene, False))
        totals = [sum(ordinary) + sum(batch) for ordinary, batch in years]
        mean = sum(totals) / len(totals)
        sd = math.sqrt(sum((value - mean) ** 2 for value in totals) / (len(totals) - 1))
        self.assertLess(abs(mean - model.uninsured()["mean"]), 3 * sd / math.sqrt(len(totals)))
        sampled = tail_stats([(value, 1.0) for value in totals])
        self.assertLess(abs(sampled["cte99"] / model.uninsured()["cte99"] - 1), 0.05)


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        evidence, assumptions = annual_report.load_inputs()
        cls.results = annual_report.build(evidence, assumptions, years=500)
        cls.stored = json.loads(annual_report.OUTPUT.read_text(encoding="utf-8"))

    def test_every_candidate_was_priced(self):
        self.assertEqual(self.results["selection"]["candidates"], 45)

    def test_the_rule_written_before_the_run_gives_this_contract(self):
        rows = self.results["selection"]["rows"]
        chosen = self.results["selection"]["chosen"]
        passing = [row for row in rows if row["cte99_cut"] >= TARGET_CUT]
        floor = min(row["mean"] for row in passing)
        self.assertGreaterEqual(chosen["cte99_cut"], TARGET_CUT)
        self.assertLessEqual(chosen["mean"] - floor, TIE_YUAN)
        self.assertEqual(chosen["deductible"], max(row["deductible"] for row in passing if row["mean"] - floor <= TIE_YUAN))

    def test_the_rule_result_is_kept_beside_the_adopted_contract(self):
        rule, adopted = self.results["rule_result"], self.results["base_contract"]
        self.assertEqual(rule, self.results["enhanced"]["contract"])
        self.assertEqual((adopted["deductible"], adopted["share"], adopted["limit"]), (100000, 0.9, 300000))
        same = next(row for row in self.results["selection"]["rows"] if (row["deductible"], row["share"], row["limit"]) == (100000, 0.9, 300000))
        self.assertLess(same["cte99_cut"], TARGET_CUT)

    def test_the_contract_file_is_the_adopted_contract(self):
        contract = AnnualContract.from_mapping(json.loads(CONTRACT_FILE.read_text(encoding="utf-8")))
        chosen = self.results["base_contract"]
        self.assertEqual(contract.annual_aggregate_deductible_cents, chosen["deductible"] * 100)
        self.assertEqual(contract.coinsurance_bp, round(chosen["share"] * 10000))
        self.assertEqual(contract.annual_limit_cents, chosen["limit"] * 100)

    def test_every_deterministic_result_matches_the_stored_file(self):
        def same(ours, theirs, path):
            if isinstance(ours, dict):
                self.assertEqual(sorted(ours), sorted(theirs), path)
                for key in ours:
                    if path == "structures" and key in ("Core", "Plus"):
                        continue  # sampled years; this run uses fewer of them
                    same(ours[key], theirs[key], f"{path}.{key}" if path else key)
            elif isinstance(ours, list):
                self.assertEqual(len(ours), len(theirs), path)
                for index, (left, right) in enumerate(zip(ours, theirs)):
                    same(left, right, f"{path}[{index}]")
            elif isinstance(ours, float):
                self.assertAlmostEqual(ours, theirs, places=4, msg=path)
            else:
                self.assertEqual(ours, theirs, path)
        same(json.loads(json.dumps(self.results, ensure_ascii=False)), self.stored, "")

    def test_the_enhanced_tier_is_the_contract_in_its_file(self):
        contract = AnnualContract.from_mapping(json.loads(ENHANCED_FILE.read_text(encoding="utf-8")))
        terms = self.results["enhanced"]["contract"]
        self.assertEqual(contract.annual_aggregate_deductible_cents, terms["deductible"] * 100)
        self.assertEqual(contract.coinsurance_bp, round(terms["share"] * 10000))
        self.assertEqual(contract.annual_limit_cents, terms["limit"] * 100)

    def test_the_enhanced_tier_beats_plus_on_all_four_measures(self):
        stronger, plus = self.stored["structures"]["enhanced"], self.stored["structures"]["Plus"]
        for measure in ("premium", "mean", "p99", "cte99"):
            self.assertLess(stronger[measure], plus[measure])

    def test_the_base_tier_beats_core_on_all_four_measures(self):
        base, core = self.stored["structures"]["aggregate"], self.stored["structures"]["Core"]
        for measure in ("premium", "mean", "p99", "cte99"):
            self.assertLess(base[measure], core[measure])

    def test_older_contracts_keep_their_terms(self):
        evidence, assumptions = annual_report.load_inputs()
        self.assertEqual(assumptions["older_contracts"]["Core"], {"deductible": 500, "share": 0.8, "occurrence_limit": 20000, "batch_limit": 150000, "annual_limit": 300000})
        self.assertEqual(assumptions["older_contracts"]["Plus"], {"deductible": 200, "share": 0.9, "occurrence_limit": 50000, "batch_limit": 300000, "annual_limit": 600000})

    def test_every_sensitivity_table_is_filled_and_moves_the_right_way(self):
        for block in (self.results["sensitivity"], self.results["enhanced"]["sensitivity"]):
            self.assertEqual(sorted(block), sorted(["难单占比", "全错故障年概率", "全错故障检查周期小时", "全错故障影响比例", "全错故障类型", "严重度倍数", "追回率"]))
            shares = block["难单占比"]
            self.assertEqual(len(shares), 5)
            self.assertEqual([row["uninsured_mean"] for row in shares], sorted(row["uninsured_mean"] for row in shares))
            self.assertLess(block["追回率"][1]["uninsured_cte99"], block["追回率"][0]["uninsured_cte99"])
            self.assertGreater(block["全错故障类型"][1]["uninsured_cte99"], block["全错故障类型"][0]["uninsured_cte99"])

    def test_more_clean_tests_lower_the_bound_and_the_price(self):
        ladder = self.results["evidence_ladder"]
        self.assertEqual([row["runs"] for row in ladder], [210, 500, 1000, 2000, 5000])
        prices = [row["premium_with_capital"] for row in ladder]
        self.assertEqual(prices, sorted(prices, reverse=True))
        self.assertLess(prices[-1], prices[0])

    def test_accumulation_counts_the_deductible_already_used(self):
        evidence, assumptions = annual_report.load_inputs()
        terms = terms_of(assumptions["base_contract"])
        plain = self.results["portfolio"][0]
        self.assertAlmostEqual(plain["paid_per_merchant"], terms.paid(plain["ordinary_loss_per_merchant"] + plain["loss_per_merchant"]))
        self.assertGreater(plain["paid_per_merchant"], terms.paid(plain["loss_per_merchant"]))
        self.assertAlmostEqual(plain["paid_all_merchants"], plain["paid_per_merchant"] * assumptions["portfolio_merchants"])

    def test_the_value_of_monitoring_is_not_counted_twice(self):
        row = next(item for item in self.results["monitoring_value"] if item["tier"] == "B" and item["frequency_basis"] == "priced")
        plain = next(item for item in self.results["tiers"] if item["tier"] == "B" and not item["monitored"])
        watched = next(item for item in self.results["tiers"] if item["tier"] == "B" and item["monitored"])
        self.assertAlmostEqual(row["uninsured"], plain["uninsured"]["mean"] - watched["uninsured"]["mean"])
        self.assertAlmostEqual(row["base"], plain["insured"]["mean_with_capital"] - watched["insured"]["mean_with_capital"])

    def test_sending_the_failing_family_to_people_lowers_the_price(self):
        after, before = self.results["after_list"], self.results["structures"]
        self.assertEqual(after["runs"], 180)
        self.assertLess(after["lambda"], 100)
        self.assertLess(after["base"]["premium_with_capital"], before["aggregate"]["premium_with_capital"])
        self.assertLess(after["enhanced"]["premium_with_capital"], before["enhanced"]["premium_with_capital"])

    def test_shared_drift_is_counted_in_the_accumulation(self):
        faults = {(row["fault"], row["case"]) for row in self.results["portfolio"]}
        self.assertIn(("drift", "plain"), faults)
        drift = next(row for row in self.results["portfolio"] if row["fault"] == "drift" and row["case"] == "plain")
        self.assertAlmostEqual(drift["annual_chance_per_merchant"], 0.10)
        self.assertGreater(drift["paid_all_merchants"], 0)

    def test_monitoring_value_at_the_likely_rate_keeps_the_priced_premium(self):
        evidence, assumptions = annual_report.load_inputs()
        scene, tier = Scenario.from_assumptions(assumptions), evidence["tiers"]["B"]
        rate = likely_frequency(tier, scene.gate_leak)
        terms = terms_of(assumptions["base_contract"])
        total = 0.0
        for monitored, sign in ((False, 1), (True, -1)):
            priced = next(row for row in self.results["tiers"] if row["tier"] == "B" and row["monitored"] is monitored)
            model, _ = model_for(evidence, tier, scene, monitored, frequency=rate)
            total += sign * (priced["insured"]["premium_with_capital"] + tail_stats([(loss - terms.paid(loss), mass) for loss, mass in model.outcomes()])["mean"])
        row = next(item for item in self.results["monitoring_value"] if item["tier"] == "B" and item["frequency_basis"] == "likely")
        self.assertAlmostEqual(row["base"], total)

    def test_likely_year_uses_the_priced_premium(self):
        likely = self.results["likely"]
        self.assertAlmostEqual(likely["premium"], self.results["structures"]["aggregate"]["premium_with_capital"])
        self.assertLess(likely["uninsured"]["mean"], self.results["structures"]["uninsured"]["mean"])

    def test_a_year_of_all_recorded_accidents_stays_inside_the_deductible(self):
        contract = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
        self.assertLess(8601926, contract["annual_aggregate_deductible_cents"])


class SummaryTests(unittest.TestCase):
    def test_the_workbench_view_only_trims_the_stored_results(self):
        summary = load_annual_summary()
        stored = json.loads(annual_report.OUTPUT.read_text(encoding="utf-8"))
        self.assertFalse(summary["commercial_quote"])
        self.assertEqual(summary["structures"][3]["premium_yuan"], round(stored["structures"]["aggregate"]["premium"]))
        self.assertEqual(len(summary["tiers"]), 8)
        self.assertEqual([row["product_tier"] for row in summary["contracts"]], ["基础档", "增强档"])
        self.assertEqual(summary["structures"][4]["label"], "增强档")

    def test_the_configuration_that_must_be_fixed_first_is_marked(self):
        marked = {row["tier"]: row["insurable"] for row in load_annual_summary()["tiers"]}
        self.assertEqual(marked, {"A": True, "B": True, "C": False, "D": False})

    def test_the_enhanced_tier_is_only_offered_where_it_is_worth_buying(self):
        offered = {row["tier"]: row["enhanced_offered"] for row in load_annual_summary()["tiers"]}
        self.assertEqual(offered, {"A": True, "B": True, "C": False, "D": False})
        stored = json.loads(annual_report.OUTPUT.read_text(encoding="utf-8"))
        for row in stored["enhanced"]["tiers"]:
            self.assertEqual(row["open"], row["ordinary_expected"] < 80000)
            if not row["open"]:
                self.assertGreater(row["insured"]["mean"], row["uninsured"]["mean"] + 10000)

    def test_the_route_needs_pairing(self):
        token, grant = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        app = create_observer("http://127.0.0.1:8999", token, grant, transport=httpx.MockTransport(lambda request: httpx.Response(404)), frontend_dir=Path("no-static"))
        client = TestClient(app, base_url="http://127.0.0.1:8810", raise_server_exceptions=False)
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        headers = {"Origin": "http://127.0.0.1:8810", "X-Workbench-Request": "1"}
        self.assertEqual(client.get("/observer/api/annual-model", headers=headers).status_code, 401)
        self.assertEqual(client.post("/observer/pair", json={"grant": grant}, headers=headers).status_code, 200)
        response = client.get("/observer/api/annual-model", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["schema"], "AgentShield.annual_summary.v0.1")


if __name__ == "__main__":
    unittest.main()
