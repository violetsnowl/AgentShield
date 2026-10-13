"""B0 pooled / B1 pre-stratified scenario cost: A0 research candidate.

Inputs are *already assessed claim payouts*, not gross B transactions. Same case
repeats are averaged before treating that case as a statistical observation.
No empirical commercial premium or credibility correction is produced.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping, Sequence
from .contracts import ContractError, _int, _text

STRATA = ("whole_low", "whole_high", "partial_low", "partial_high")
VALID_SOURCES = frozenset({"scripted_test", "mock_agent", "observed_agent_execution", "engineering_injection"})


def _decimal_string(x: Decimal | None) -> str | None:
    return None if x is None else format(x.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), ".4f")


def _weight(x: Any, key: str) -> Decimal:
    if isinstance(x, bool) or not isinstance(x, (int, float, str, Decimal)):
        raise ContractError(f"weight {key} must be a finite decimal number")
    try:
        d = Decimal(str(x))
    except InvalidOperation as exc:
        raise ContractError(f"invalid weight {key}") from exc
    if not d.is_finite() or d < 0 or d > 1:
        raise ContractError(f"invalid range for weight {key}")
    return d


def _validate_weights(weights: Mapping[str, Any]) -> dict[str, Decimal]:
    if not isinstance(weights, Mapping) or set(weights) != set(STRATA):
        raise ContractError("target_weights must contain exactly four predeclared strata")
    out = {key: _weight(weights[key], key) for key in STRATA}
    if sum(out.values()) != Decimal(1):
        raise ContractError("target_weights must sum to exactly 1")
    return out


def _validate_records(records: Sequence[Mapping[str, Any]], config_id: str) -> tuple[dict, list, list]:
    if not isinstance(records, (list, tuple)):
        raise ContractError("records must be a list or tuple")
    case_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)
    case_attrs = {}
    split_by_case = {}
    parent_split = {}
    parent_owners = {}
    seen_run = set()
    sources = set()
    for row in records:
        if not isinstance(row, Mapping):
            raise ContractError("each record must be a mapping")
        for req in ("run_id", "case_id", "config_id", "split", "stratum", "claim_status", "payout_cents", "execution_source"):
            if req not in row:
                raise ContractError(f"missing run field: {req}")
        run_id = _text(row["run_id"], "run_id")
        case_id = _text(row["case_id"], "case_id")
        if run_id in seen_run:
            raise ContractError("duplicate run_id detected")
        seen_run.add(run_id)
        if row["config_id"] != config_id:
            raise ContractError("mixed config_id must be estimated separately")
        split, stratum = row["split"], row["stratum"]
        if split not in ("estimation", "holdout") or stratum not in STRATA:
            raise ContractError("unsupported split / stratum")
        if row["claim_status"] not in ("assessed", "not_covered", "needs_review"):
            raise ContractError("unsupported claim_status")
        payout = row["payout_cents"]
        if row["claim_status"] == "needs_review":
            if payout is not None:
                raise ContractError("needs_review payout must be null, not zero")
        else:
            _int(payout, "payout_cents")
            if row["claim_status"] == "not_covered" and payout != 0:
                raise ContractError("not_covered payout must be zero")
        source = row["execution_source"]
        if source not in VALID_SOURCES:
            raise ContractError("unsupported execution_source")
        sources.add(source)
        parent = row.get("parent_case_id")
        if parent is not None:
            parent = _text(parent, "parent_case_id")
        parent_key = parent or case_id
        if case_id in split_by_case and split_by_case[case_id] != split:
            raise ContractError("same case leaked across estimation and holdout")
        split_by_case[case_id] = split
        if parent_key in parent_split and parent_split[parent_key] != split:
            raise ContractError("parent/near-variant group leaked across estimation and holdout")
        parent_split[parent_key] = split
        if parent_key in parent_owners and parent_owners[parent_key] != case_id:
            raise ContractError("multiple case IDs share a parent: not independent observations")
        parent_owners[parent_key] = case_id
        key = (split, case_id)
        attr = (stratum, source, parent_key)
        if key in case_attrs and case_attrs[key] != attr:
            raise ContractError("repeats of one case disagree on strata/source/parent")
        case_attrs[key] = attr
        case_rows[key].append(dict(row))
    if len(sources) > 1:
        raise ContractError("do not mix engineering, mock, scripted and real Agent data")
    cases_by_split: dict[str, list[dict]] = {"estimation": [], "holdout": []}
    for (split, case_id), rows in case_rows.items():
        amounts = [r["payout_cents"] for r in rows]
        complete = all(amount is not None for amount in amounts)
        cases_by_split[split].append({
            "case_id": case_id,
            "stratum": rows[0]["stratum"],
            "runs": len(rows),
            "fully_assessed": complete,
            "case_mean_cents": (sum(Decimal(x) for x in amounts) / Decimal(len(amounts))) if complete else None,
        })
    return {"source": next(iter(sources)) if sources else None, "run_count": len(records)}, cases_by_split["estimation"], cases_by_split["holdout"]


def _summarize(cases: list[dict], weights: dict[str, Decimal]) -> dict:
    valid = [r for r in cases if r["fully_assessed"]]
    grouped = {s: [r["case_mean_cents"] for r in valid if r["stratum"] == s] for s in STRATA}
    means = {s: sum(values) / Decimal(len(values)) if values else None for s, values in grouped.items()}
    pooled = sum(r["case_mean_cents"] for r in valid) / Decimal(len(valid)) if valid else None
    supported = all(means[s] is not None for s in STRATA if weights[s] > 0)
    stratified = sum(means[s] * weights[s] for s in STRATA if weights[s] > 0) if supported else None
    return {
        "case_count": len(cases),
        "assessed_case_count": len(valid),
        "unverified_case_count": len(cases) - len(valid),
        "stratum_counts": {s: len(grouped[s]) for s in STRATA},
        "stratum_mean_cents_decimal": {s: _decimal_string(means[s]) for s in STRATA},
        "pooled_mean_cents_decimal": _decimal_string(pooled),
        "pooled": pooled,
        "stratified": stratified,
        "missing_target_strata": [s for s in STRATA if weights[s] > 0 and means[s] is None],
    }


def calculate_quote(
    records: Sequence[Mapping[str, Any]], *, config_id: str,
    contract_version: str, data_version: str, run_manifest_ref: str,
    target_weights: Mapping[str, Any], target_volume: int,
    reviewed_evidence: bool = False,
) -> dict[str, Any]:
    """QuoteResult candidate; not a commercial premium and no claim validation.

    `reviewed_evidence=True` is reserved for independent A/C acceptance. It does
    not establish authenticity by itself. Engineering/scripted runs always remain
    illustrative. Missing/unknown cases block complete scenario estimates.
    """
    config_id = _text(config_id, "config_id")
    contract_version = _text(contract_version, "contract_version")
    data_version = _text(data_version, "data_version")
    run_manifest_ref = _text(run_manifest_ref, "run_manifest_ref")
    volume = _int(target_volume, "target_volume", minimum=1)
    if type(reviewed_evidence) is not bool:
        raise ContractError("reviewed_evidence must be bool")
    weights = _validate_weights(target_weights)
    provenance, estimate_cases, holdout_cases = _validate_records(records, config_id)
    dev = _summarize(estimate_cases, weights)
    holdout = _summarize(holdout_cases, weights)
    full = (dev["case_count"] > 0 and dev["unverified_case_count"] == 0
            and not dev["missing_target_strata"])
    # Zero observed payouts are compatible with positive but unobserved risk.
    positive_observed = any(c["case_mean_cents"] is not None and c["case_mean_cents"] > 0 for c in estimate_cases)
    if not full or not positive_observed:
        status = "insufficient_evidence" if dev["case_count"] == 0 or dev["missing_target_strata"] or not positive_observed else "partial"
    else:
        status = "illustrative"  # A0 never self-asserts validated commercial pricing.
    complete_costs = full and positive_observed
    b0 = dev["pooled"]
    b1 = dev["stratified"]
    holdout_reference = (holdout["stratified"] if holdout["case_count"] > 0
                         and holdout["unverified_case_count"] == 0
                         and not holdout["missing_target_strata"] else None)
    result = {
        "schema_version": "a-quote-v0.1-candidate",
        "commercial_quote": False,
        "status": status,
        "scope": "ecommerce_refund_ai_agent_research_only",
        "contract_version": contract_version,
        "data_version": data_version,
        "calculation_version": "actuarial-a0-0.1",
        "run_manifest_ref": run_manifest_ref,
        "config_id": config_id,
        "execution_source": provenance["source"],
        "reviewed_evidence": reviewed_evidence,
        "target_volume": volume,
        "target_weights": {s: str(weights[s]) for s in STRATA},
        "run_count": provenance["run_count"],
        "estimation": {k: v for k, v in dev.items() if k not in ("pooled", "stratified")},
        "holdout": {k: v for k, v in holdout.items() if k not in ("pooled", "stratified")},
        "methods": {
            "B0": {"label": "unstratified_case_mean", "estimated_mean_cents_decimal": _decimal_string(b0),
                   "scenario_cost_cents_decimal": _decimal_string(b0 * volume) if complete_costs else None},
            "B1": {"label": "prestratified_weighted_case_mean", "estimated_mean_cents_decimal": _decimal_string(b1),
                   "scenario_cost_cents_decimal": _decimal_string(b1 * volume) if complete_costs and b1 is not None else None},
            "B2": {"status": "not_fitted", "estimated_mean_cents_decimal": None,
                   "scenario_cost_cents_decimal": None},
        },
        "holdout_evaluation": {"reference_cents_decimal": _decimal_string(holdout_reference),
            "B0_abs_error_cents_decimal": _decimal_string(abs(b0 - holdout_reference))
                if b0 is not None and holdout_reference is not None else None,
            "B1_abs_error_cents_decimal": _decimal_string(abs(b1 - holdout_reference))
                if b1 is not None and holdout_reference is not None else None,
            "interpretation": "holdout_sample_reference_not_population_truth"},
        "limitations": ["source labels require independent verification",
                        "engineering runs cannot estimate real failure frequency",
                        "B0/B1 are pure-risk-cost scenarios, not commercial premiums",
                        "no credible zero-risk conclusion from zero observed payouts"],
    }
    return result
