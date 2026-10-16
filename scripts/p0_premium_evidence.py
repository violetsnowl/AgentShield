"""Conservative premium-evidence gate. No numerical premium without explicit inputs.

If the user supplies assumed per-task payouts, compute only a labeled pure risk
cost study illustration (no aggregate, no commercial premium).
"""
from __future__ import annotations
import argparse
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

STRATA = ("whole_low", "whole_high", "partial_low", "partial_high")


def assess(raw: dict) -> dict:
    missing = []
    V = raw.get("annual_agent_task_volume")
    if type(V) is not int or V < 0:
        missing.append("annual_agent_task_volume")
    weights = raw.get("target_weights")
    if not isinstance(weights, dict) or set(weights) != set(STRATA):
        missing.append("target_weights[4 strata]")
    else:
        try:
            w = {k: Decimal(str(weights[k])) for k in STRATA}
            if any(v < 0 for v in w.values()) or abs(sum(w.values()) - 1) > Decimal("0.0000001"):
                missing.append("target_weights summing to 1")
        except Exception:
            missing.append("target_weights numeric validity")
    payouts = raw.get("estimated_payout_cents_per_task_by_product")
    if not isinstance(payouts, dict):
        missing.append("estimated_payout_cents_per_task_by_product")
    else:
        for name in ("AgentShield-Core", "AgentShield-Plus"):
            p = payouts.get(name)
            if not isinstance(p, dict) or set(p) != set(STRATA):
                missing.append(f"{name} payout means for four strata")
            else:
                try:
                    vals = [Decimal(str(p[k])) for k in STRATA]
                    if any(v < 0 or not v.is_finite() for v in vals):
                        raise ValueError("invalid")
                except Exception:
                    missing.append(f"{name} valid nonnegative payout means")
    assumption_label = raw.get("estimate_source")
    if assumption_label not in ("research_assumption", "reviewed_estimation_sample"):
        missing.append("estimate_source (research_assumption or reviewed_estimation_sample)")
    if assumption_label == "reviewed_estimation_sample" and not raw.get("reviewed_estimation_reference"):
        missing.append("reviewed_estimation_reference")
    if missing:
        return {"schema":"AgentShield.A_P0_premium_evidence.v0.1","status":"insufficient_evidence",
                "annual_pure_risk_cost_cents":None,"commercial_premium_cents":None,
                "missing_inputs": sorted(set(missing)),"commercial_quote":False}
    res = {}
    for name in ("AgentShield-Core", "AgentShield-Plus"):
        mu = payouts[name]
        value = Decimal(V) * sum(w[k] * Decimal(str(mu[k])) for k in STRATA)
        res[name] = int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return {"schema":"AgentShield.A_P0_premium_evidence.v0.1",
            "status":"illustrative_assumptions_only" if assumption_label=="research_assumption" else "research_estimation_subject_to_scope",
            "annual_pure_risk_cost_cents":res, "commercial_premium_cents":None,
            "annual_aggregate_applied":False,"commercial_quote":False,
            "formula":"V * sum_g(w_g * mean_indemnity_cents_per_task_g)",
            "estimate_source":assumption_label,
            "warning":"No annual aggregate reduction, expense loading, premium taxes, capital cost, or commercial pricing applied"}


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a=p.parse_args(argv)
    result=assess(json.loads(a.input.read_text(encoding="utf-8")))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"output":str(a.output)},ensure_ascii=False))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
