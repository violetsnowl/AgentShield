"""Price the rating tiers and pick the contract by the rule fixed in ACTUARIAL_ANNUAL_V0.2 section 5.

  python -m experiments.annual_report            all tables, written to configs/insurance
  python -m experiments.annual_report --quick    fewer sampled years, for tests

Reads the evidence file made by experiments.annual_calibration; it never reads raw runs.
Version 0.2 of the results follows the review in section 9 of that record; version 0.1 stays on disk.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import json
from math import comb
from typing import Any

from actuarial.annual import AggregateTerms, AnnualLossModel, PerEventTerms, PremiumBasis, evaluate_sampled, simulate_years, tail_stats
from experiments.claim_pack import ROOT
from experiments.risk_summary import wilson

EVIDENCE = ROOT / "configs/insurance/annual_evidence_v0.2.json"
ASSUMPTIONS = ROOT / "configs/insurance/annual_assumptions_v0.2.json"
OUTPUT = ROOT / "configs/insurance/annual_results_v0.2.json"
REFERENCE_TIER = "B"
TARGET_CUT = 0.40
TIE_YUAN = 500.0
SAMPLED_YEARS = 100000
ATOMS = 4


@dataclass(frozen=True)
class Scenario:
    """Everything one model run depends on, so a sensitivity changes one field and nothing else."""
    tasks: float
    hours: float
    hard_share: float
    gate_leak: float
    recovery: float
    drift_chance: float
    drift_cycle: float
    loud_chance: float
    loud_cycle: float
    round_hours: float
    response_hours: float
    catch_share: float
    severity_scale: float = 1.0
    loud_share: float = 1.0
    loud_kind: str = "whole_order"

    @classmethod
    def from_assumptions(cls, raw: dict[str, Any]) -> "Scenario":
        watch, loud = raw["monitoring"], raw["loud_fault"]
        return cls(raw["annual_tasks"], raw["hours_per_year"], raw["hard_task_share"], raw["gate_leak"], raw["recovery_rate"],
                   raw["quiet_drift"]["annual_chance"], raw["quiet_drift"]["cycle_hours"], loud["annual_chance"], loud["cycle_hours"],
                   watch["round_hours"], watch["response_hours"], watch["catch_share"], loud_share=loud["affected_share"])


def severity_points(evidence: dict[str, Any], scale: float = 1.0) -> list[tuple[float, float]]:
    return [(cents * scale / 100, 1.0) for cents in evidence["severity"]["task_mean_cents"]]


def pricing_frequency(tier: dict[str, Any], leak: float) -> float:
    """Upper bound for an open configuration; a gate never gets credit for its structural zero alone."""
    own = tier["evidence"]["wilson_high"]
    return max(own, leak * tier["open_reference"]["wilson_high"]) if tier["gate"] else own


def likely_rate(arm: dict[str, Any]) -> float:
    return (arm["accidents"] + 0.5) / (arm["runs"] + 1)


def likely_frequency(tier: dict[str, Any], leak: float) -> float:
    """The posterior mean under a Jeffreys prior: what we would bet on, as opposed to what we price at."""
    own = likely_rate(tier["evidence"])
    return max(own, leak * likely_rate(tier["open_reference"])) if tier["gate"] else own


def hours_across(cycle: float, response: float = 0.0) -> list[float]:
    """A fault starts anywhere in the check cycle, so its duration is uniform; each atom is the midpoint of its quarter."""
    return [cycle * (2 * index + 1) / (2 * ATOMS) + response for index in range(ATOMS)]


def batch_events(evidence: dict[str, Any], tier: dict[str, Any], scene: Scenario, monitored: bool, frequency: float | None = None) -> list[list[tuple[float, float]]]:
    per_hour = scene.tasks / scene.hours
    mean_loss = evidence["severity"]["mean_cents"] * scene.severity_scale / 100
    worst_arm = next(item["evidence"] for item in evidence["tiers"].values() if item["thinking_off"] and not item["gate"])
    frequency = pricing_frequency(tier, scene.gate_leak) if frequency is None else frequency
    leak = scene.gate_leak if tier["gate"] else 1.0
    # Ordinary events already run at the tier's own rate through the window, so drift only adds the gap.
    # A gate lets through its leak of the drifted rate, and that is the figure the tier's rate is compared with.
    extra_rate = max(worst_arm["accidents"] / worst_arm["runs"] * leak - frequency, 0.0)
    loud_per_task = evidence["natural_flow"][f"{scene.loud_kind}_per_task_cents"] * scene.loud_share * scene.severity_scale / 100
    keep = 1 - scene.recovery

    def event(chance: float, cycle: float, per_task: float) -> list[tuple[float, float]]:
        amount = per_hour * per_task * keep
        if not monitored:
            return [(chance / ATOMS, amount * hours) for hours in hours_across(cycle)]
        caught = [(chance * scene.catch_share / ATOMS, amount * hours) for hours in hours_across(scene.round_hours, scene.response_hours)]
        missed = [(chance * (1 - scene.catch_share) / ATOMS, amount * hours) for hours in hours_across(cycle)]
        return caught + missed

    events = [event(scene.loud_chance, scene.loud_cycle, loud_per_task * leak)]
    if not tier["thinking_off"]:
        events.append(event(scene.drift_chance, scene.drift_cycle, scene.hard_share * extra_rate * mean_loss))
    return events


def model_for(evidence: dict[str, Any], tier: dict[str, Any], scene: Scenario, monitored: bool, *, frequency: float | None = None) -> tuple[AnnualLossModel, float]:
    rate = pricing_frequency(tier, scene.gate_leak) if frequency is None else frequency
    lam = scene.tasks * scene.hard_share * rate
    return AnnualLossModel(lam, severity_points(evidence, scene.severity_scale), batch_events(evidence, tier, scene, monitored, rate)), lam


def choose(evidence: dict[str, Any], assumptions: dict[str, Any], scene: Scenario, basis: PremiumBasis, measure: str = "mean") -> dict[str, Any]:
    model, _ = model_for(evidence, evidence["tiers"][REFERENCE_TIER], scene, False)
    bare = model.uninsured()
    rows = []
    for deductible in assumptions["candidates"]["deductibles"]:
        for share in assumptions["candidates"]["shares"]:
            for limit in assumptions["candidates"]["limits"]:
                row = model.evaluate(AggregateTerms(float(deductible), share, float(limit)), basis)
                rows.append({"deductible": deductible, "share": share, "limit": limit, "cte99_cut": 1 - row["cte99"] / bare["cte99"],
                             "cte99_cut_with_capital": 1 - row["cte99_with_capital"] / bare["cte99"], **row})
    passing = [row for row in rows if row["cte99_cut"] >= TARGET_CUT]
    if passing:
        floor = min(row[measure] for row in passing)
        chosen = max((row for row in passing if row[measure] - floor <= TIE_YUAN), key=lambda row: (row["deductible"], -row[measure]))
        how = "按规则选出"
    else:
        chosen = max(rows, key=lambda row: row["cte99_cut"])
        how = "没有方案达到 40%，取降幅最大"
    return {"uninsured": bare, "rows": rows, "passing": len(passing), "chosen": chosen, "how": how}


def terms_of(row: dict[str, Any]) -> AggregateTerms:
    return AggregateTerms(float(row["deductible"]), row["share"], float(row["limit"]))


def tier_table(evidence: dict[str, Any], scene: Scenario, basis: PremiumBasis, terms: AggregateTerms) -> list[dict[str, Any]]:
    out = []
    for key, tier in evidence["tiers"].items():
        for monitored in (False, True):
            model, lam = model_for(evidence, tier, scene, monitored)
            ordinary = lam * model.mean_severity
            out.append({"tier": key, "label": tier["label"], "monitored": monitored, "accidents": tier["evidence"]["accidents"], "runs": tier["evidence"]["runs"],
                        "frequency": pricing_frequency(tier, scene.gate_leak), "lambda": lam, "ordinary_expected": ordinary, "open": ordinary < terms.deductible,
                        "uninsured": model.uninsured(), "insured": model.evaluate(terms, basis)})
    return out


def at_likely_frequency(evidence: dict[str, Any], scene: Scenario, basis: PremiumBasis, terms: AggregateTerms) -> dict[str, Any]:
    """The premium stays priced at the upper bound; the year is drawn at the likely rate, which is what the buyer probably lives through."""
    tier = evidence["tiers"][REFERENCE_TIER]
    priced, _ = model_for(evidence, tier, scene, False)
    rate = likely_frequency(tier, scene.gate_leak)
    model, lam = model_for(evidence, tier, scene, False, frequency=rate)
    premium = priced.evaluate(terms, basis)["premium_with_capital"]
    outcomes = model.outcomes()
    paid = tail_stats([(terms.paid(loss), mass) for loss, mass in outcomes])["mean"]
    bare = model.uninsured()
    spend = tail_stats([(premium + loss - terms.paid(loss), mass) for loss, mass in outcomes])
    return {"frequency": rate, "lambda": lam, "uninsured": bare, "premium": premium, "expected_paid": paid, "insured": spend, "cte99_cut": 1 - spend["cte99"] / bare["cte99"],
            "trigger_chance": sum(mass for loss, mass in outcomes if terms.paid(loss) > 0), "loss_ratio": paid / premium}


def monitoring_value(evidence: dict[str, Any], scene: Scenario, basis: PremiumBasis, terms: AggregateTerms, enhanced: AggregateTerms) -> list[dict[str, Any]]:
    """Fall in mean yearly spend from buying monitoring. Premium and paid claims move together, so neither is added on top."""
    out = []
    for key in ("A", "B"):
        tier = evidence["tiers"][key]
        priced = {monitored: model_for(evidence, tier, scene, monitored)[0] for monitored in (False, True)}

        def spend(rate: float, monitored: bool, cover: AggregateTerms) -> float:
            premium = priced[monitored].evaluate(cover, basis)["premium_with_capital"]
            model, _ = model_for(evidence, tier, scene, monitored, frequency=rate)
            return premium + tail_stats([(loss - cover.paid(loss), mass) for loss, mass in model.outcomes()])["mean"]

        for label, rate in (("priced", pricing_frequency(tier, scene.gate_leak)), ("likely", likely_frequency(tier, scene.gate_leak))):
            plain, _ = model_for(evidence, tier, scene, False, frequency=rate)
            watched, _ = model_for(evidence, tier, scene, True, frequency=rate)
            out.append({"tier": key, "frequency_basis": label, "uninsured": plain.uninsured()["mean"] - watched.uninsured()["mean"],
                        "base": spend(rate, False, terms) - spend(rate, True, terms), "enhanced": spend(rate, False, enhanced) - spend(rate, True, enhanced)})
    return out


def after_authorization_list(evidence: dict[str, Any], scene: Scenario, basis: PremiumBasis, terms: AggregateTerms, enhanced: AggregateTerms) -> dict[str, Any]:
    """The worst low-thinking arm had its one accident in one family. Send that family to people and price what is left."""
    tier = evidence["tiers"][REFERENCE_TIER]
    runs = tier["evidence"]["runs"] * 6 // 7
    rate = wilson(0, runs)[1]
    narrowed = replace(scene, hard_share=scene.hard_share * 6 / 7)
    model, lam = model_for(evidence, tier, narrowed, False, frequency=rate)
    return {"runs": runs, "frequency": rate, "lambda": lam, "ordinary_expected": lam * model.mean_severity, "uninsured": model.uninsured(),
            "base": model.evaluate(terms, basis), "enhanced": model.evaluate(enhanced, basis)}


def structure_table(evidence: dict[str, Any], assumptions: dict[str, Any], scene: Scenario, basis: PremiumBasis, terms: AggregateTerms, enhanced: AggregateTerms, years: int) -> dict[str, Any]:
    tier = evidence["tiers"][REFERENCE_TIER]
    model, lam = model_for(evidence, tier, scene, False)
    events = batch_events(evidence, tier, scene, False)
    sampled = simulate_years(years, 20261106, lam, severity_points(evidence, scene.severity_scale), events)
    batch_chance = sum(chance for event in events for chance, _ in event)
    amounts = [cents / 100 for cents in evidence["severity"]["task_mean_cents"]]
    out = {"uninsured": model.uninsured(), "aggregate": model.evaluate(terms, basis), "enhanced": model.evaluate(enhanced, basis)}
    for name, raw in assumptions["older_contracts"].items():
        share_paid = sum(1 for amount in amounts if amount > raw["deductible"]) / len(amounts)
        handling = basis.case_cost * (lam * share_paid + batch_chance)
        out[name] = evaluate_sampled(sampled, PerEventTerms(**raw), basis, handling=handling)
    return out


def sensitivity(evidence: dict[str, Any], scene: Scenario, basis: PremiumBasis, terms: AggregateTerms) -> dict[str, list[dict[str, Any]]]:
    tier = evidence["tiers"][REFERENCE_TIER]
    cases = {"难单占比": [("hard_share", value) for value in (0.01, 0.02, 0.05, 0.10, 0.20)],
             "全错故障年概率": [("loud_chance", value) for value in (0.005, 0.01, 0.02, 0.05)],
             "全错故障检查周期小时": [("loud_cycle", value) for value in (6.0, 12.0, 24.0, 72.0)],
             "全错故障影响比例": [("loud_share", value) for value in (0.25, 0.5, 1.0)],
             "全错故障类型": [("loud_kind", value) for value in ("whole_order", "duplicate")],
             "严重度倍数": [("severity_scale", value) for value in (1.0, 2.0)],
             "追回率": [("recovery", value) for value in (0.0, 0.3)]}
    out: dict[str, list[dict[str, Any]]] = {}
    for name, changes in cases.items():
        rows = []
        for field, value in changes:
            model, lam = model_for(evidence, tier, replace(scene, **{field: value}), False)
            bare, row = model.uninsured(), model.evaluate(terms, basis)
            rows.append({"value": value, "lambda": lam, "uninsured_mean": bare["mean"], "uninsured_cte99": bare["cte99"], "premium": row["premium"], "insured_mean": row["mean"],
                         "insured_cte99": row["cte99"], "cut": 1 - row["cte99"] / bare["cte99"], "premium_with_capital": row["premium_with_capital"],
                         "cut_with_capital": 1 - row["cte99_with_capital"] / bare["cte99"]})
        out[name] = rows
    return out


def evidence_ladder(evidence: dict[str, Any], scene: Scenario, basis: PremiumBasis, terms: AggregateTerms) -> list[dict[str, Any]]:
    """What a cleaner test record is worth: zero accidents on more tasks lowers the upper bound."""
    tier = evidence["tiers"][REFERENCE_TIER]
    cheap, dear = evidence["tiers"]["A"]["evidence"]["cost_per_run_cny"], tier["evidence"]["cost_per_run_cny"]
    out = []
    for runs in (210, 500, 1000, 2000, 5000):
        high = wilson(0, runs)[1]
        model, lam = model_for(evidence, tier, scene, False, frequency=high)
        row = model.evaluate(terms, basis)
        out.append({"runs": runs, "frequency": high, "lambda": lam, "expected_ordinary_loss": lam * model.mean_severity, "uninsured_mean": model.uninsured()["mean"], "premium": row["premium"],
                    "premium_with_capital": row["premium_with_capital"], "insured_mean": row["mean"], "insured_cte99": row["cte99"], "test_cost_low": runs * cheap, "test_cost_high": runs * dear})
    return out


def latency_table(evidence: dict[str, Any], scene: Scenario) -> list[dict[str, Any]]:
    per_task = evidence["natural_flow"]["whole_order_per_task_cents"] / 100
    per_hour = scene.tasks / scene.hours
    return [{"hours": hours, "loud_fault_loss": per_hour * per_task * hours} for hours in (1.0, 2.5, 4.0, 12.0, 24.0, 72.0)]


def sentinel_table(evidence: dict[str, Any], scene: Scenario, round_hours: float) -> list[dict[str, Any]]:
    bad = evidence["sentinel"]["off"]
    good = evidence["sentinel"]["low"]
    rate_bad, rate_good = bad["accidents"] / bad["runs"], good["accidents"] / good["runs"]
    rounds = scene.hours / round_hours
    cheap, dear = good["cost_per_run_cny"], evidence["tiers"]["B"]["evidence"]["cost_per_run_cny"]

    def at_least(k: int, n: int, p: float) -> float:
        return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))

    out = []
    for n, k in ((10, 2), (10, 3), (20, 3), (20, 4)):
        false_alarm = at_least(k, n, rate_good)
        out.append({"tasks": n, "threshold": k, "catch_drift": at_least(k, n, rate_bad), "false_alarm_round": false_alarm, "false_alarms_year": false_alarm * rounds,
                    "false_alarms_year_upper": at_least(k, n, good["wilson_high"]) * rounds, "model_cost_low": n * rounds * cheap, "model_cost_high": n * rounds * dear})
    return out


def portfolio(evidence: dict[str, Any], scene: Scenario, basis: PremiumBasis, terms: AggregateTerms, merchants: int) -> list[dict[str, Any]]:
    """A shared model or vendor fault can hit every merchant at once, so a loud fault does not diversify."""
    out = []
    tier = evidence["tiers"][REFERENCE_TIER]
    for monitored in (False, True):
        model, lam = model_for(evidence, tier, scene, monitored)
        ordinary = lam * model.mean_severity
        priced = model.evaluate(terms, basis)
        premiums = priced["premium_with_capital"] * merchants
        for fault, atoms in zip(("loud", "drift"), batch_events(evidence, tier, scene, monitored)):
            groups = [("caught", atoms[:ATOMS]), ("missed", atoms[ATOMS:])] if monitored else [("plain", atoms)]
            for name, group in groups:
                chance, amount = sum(item[0] for item in group), max(item[1] for item in group)
                # Ordinary losses have already used part of the deductible by the time a fault lands.
                paid = terms.paid(ordinary + amount)
                out.append({"fault": fault, "monitored": monitored, "case": name, "annual_chance_per_merchant": chance, "loss_per_merchant": amount, "ordinary_loss_per_merchant": ordinary,
                            "paid_per_merchant": paid, "paid_all_merchants": paid * merchants, "premium_all_merchants": premiums,
                            "years_of_premium": paid * merchants / premiums if premiums else 0.0, "loss_ratio": priced["expected_paid"] / priced["premium_with_capital"]})
    return out


def build(evidence: dict[str, Any], assumptions: dict[str, Any], *, years: int = SAMPLED_YEARS) -> dict[str, Any]:
    scene = Scenario.from_assumptions(assumptions)
    basis = PremiumBasis(**assumptions["premium"])
    selection = choose(evidence, assumptions, scene, basis)
    with_capital = choose(evidence, assumptions, scene, basis, "mean_with_capital")
    terms = terms_of(assumptions["base_contract"])
    enhanced = terms_of(assumptions["enhanced_contract"])
    merchants = assumptions["portfolio_merchants"]
    return {"schema": "AgentShield.annual_results.v0.2", "commercial_quote": False, "base_contract": assumptions["base_contract"],
            "rule_result": {key: selection["chosen"][key] for key in ("deductible", "share", "limit")},
            "selection": {"how": selection["how"], "passing": selection["passing"], "candidates": len(selection["rows"]), "uninsured": selection["uninsured"], "chosen": selection["chosen"], "rows": selection["rows"],
                          "chosen_with_capital": {key: with_capital["chosen"][key] for key in ("deductible", "share", "limit")}},
            "tiers": tier_table(evidence, scene, basis, terms), "structures": structure_table(evidence, assumptions, scene, basis, terms, enhanced, years),
            "sensitivity": sensitivity(evidence, scene, basis, terms), "evidence_ladder": evidence_ladder(evidence, scene, basis, terms),
            "latency": latency_table(evidence, scene), "sentinel": sentinel_table(evidence, scene, assumptions["monitoring"]["round_hours"]),
            "portfolio": portfolio(evidence, scene, basis, terms, merchants), "likely": at_likely_frequency(evidence, scene, basis, terms),
            "monitoring_value": monitoring_value(evidence, scene, basis, terms, enhanced), "after_list": after_authorization_list(evidence, scene, basis, terms, enhanced),
            "enhanced": {"contract": assumptions["enhanced_contract"], "tiers": tier_table(evidence, scene, basis, enhanced), "sensitivity": sensitivity(evidence, scene, basis, enhanced),
                         "portfolio": portfolio(evidence, scene, basis, enhanced, merchants), "likely": at_likely_frequency(evidence, scene, basis, enhanced)}}


def load_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    return json.loads(EVIDENCE.read_text(encoding="utf-8")), json.loads(ASSUMPTIONS.read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    results = build(*load_inputs(), years=2000 if args.quick else SAMPLED_YEARS)
    if not args.quick:
        OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(results["base_contract"], ensure_ascii=False), json.dumps(results["rule_result"], ensure_ascii=False), results["selection"]["how"], results["selection"]["passing"])
