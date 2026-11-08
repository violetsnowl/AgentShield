"""Annual model: ordinary events, batch events and an annual aggregate deductible.

Standard library only, like the rest of `actuarial`. The claim ledger is exact integer cents.
Loss distributions are floats in yuan on a fixed grid: Panjer recursion for the ordinary events,
then a convolution with each batch event. `simulate_years` repeats the same model by sampling so
the two can check each other, and also prices contracts whose payout depends on each single event.

Nothing here is a commercial quote; see docs/decisions/ACTUARIAL_ANNUAL_V0.2.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, exp, log, sqrt
import random
from typing import Any, Mapping, Sequence

from .contracts import ContractError, _int, _text

COVERAGE_STATUSES = frozenset({"covered", "excluded", "needs_review"})
LOSS_STATUSES = frozenset({"verified", "needs_review"})
RESCALE = 1e250


@dataclass(frozen=True)
class AnnualContract:
    contract_version: str
    currency: str
    annual_aggregate_deductible_cents: int
    coinsurance_bp: int
    annual_limit_cents: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "AnnualContract":
        if not isinstance(raw, Mapping):
            raise ContractError("contract must be a mapping")
        for key in ("contract_version", "currency", "annual_aggregate_deductible_cents", "coinsurance_bp",
                    "annual_limit_cents", "commercial_quote"):
            if key not in raw:
                raise ContractError(f"missing contract field: {key}")
        if raw["commercial_quote"] is not False:
            raise ContractError("research contract must set commercial_quote=false")
        if raw["currency"] != "CNY":
            raise ContractError("only CNY is supported")
        return cls(
            contract_version=_text(raw["contract_version"], "contract_version"),
            currency="CNY",
            annual_aggregate_deductible_cents=_int(raw["annual_aggregate_deductible_cents"], "annual_aggregate_deductible_cents"),
            coinsurance_bp=_int(raw["coinsurance_bp"], "coinsurance_bp", maximum=10000),
            annual_limit_cents=_int(raw["annual_limit_cents"], "annual_limit_cents", minimum=1),
        )

    def paid_to_date(self, covered_loss_cents: int) -> int:
        eligible = max(covered_loss_cents - self.annual_aggregate_deductible_cents, 0)
        return min(self.annual_limit_cents, (eligible * self.coinsurance_bp + 5000) // 10000)


def annual_ledger(events: Sequence[Mapping[str, Any]], contract: Mapping[str, Any] | AnnualContract) -> dict[str, Any]:
    """Post a policy year event by event, in time order.

    Each payout is the change in cumulative paid, so the year adds up exactly to the aggregate
    formula. An event whose amount is unknown stays null, and later events wait for it because
    the running total is not known yet. Excluded events do not erode the deductible.
    """
    c = contract if isinstance(contract, AnnualContract) else AnnualContract.from_mapping(contract)
    rows, covered, paid, held = [], 0, 0, False
    for event in sorted(_checked(events), key=lambda row: (row["occurred_at"], row["event_id"])):
        amount = event["net_loss_cents"]
        row = {"event_id": event["event_id"], "occurred_at": event["occurred_at"], "net_loss_cents": amount,
               "coverage_status": event["coverage_status"], "loss_status": event["loss_status"], "payout_cents": None,
               "retained_loss_cents": None, "cumulative_covered_loss_cents": None, "deductible_remaining_cents": None}
        if event["loss_status"] != "verified" or event["coverage_status"] == "needs_review":
            held = True
            row["claim_status"] = "needs_review"
        elif event["coverage_status"] == "excluded":
            row.update(claim_status="not_covered", payout_cents=0, retained_loss_cents=amount)
        elif held:
            row["claim_status"] = "held_for_prior_event"
        else:
            covered += amount
            payout = c.paid_to_date(covered) - paid
            paid += payout
            row.update(claim_status="assessed", payout_cents=payout, retained_loss_cents=amount - payout,
                       cumulative_covered_loss_cents=covered,
                       deductible_remaining_cents=max(c.annual_aggregate_deductible_cents - covered, 0))
        rows.append(row)
    return {"contract_version": c.contract_version, "currency": c.currency, "events": rows,
            "covered_loss_cents": covered, "paid_cents": paid, "complete": not held, "commercial_quote": False}


def _checked(events: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    seen = set()
    for event in events:
        if not isinstance(event, Mapping):
            raise ContractError("event must be a mapping")
        for key in ("event_id", "occurred_at", "net_loss_cents", "loss_status", "coverage_status"):
            if key not in event:
                raise ContractError(f"missing event field: {key}")
        event_id = _text(event["event_id"], "event_id")
        if event_id in seen:
            raise ContractError("duplicate event_id")
        seen.add(event_id)
        if event["loss_status"] not in LOSS_STATUSES or event["coverage_status"] not in COVERAGE_STATUSES:
            raise ContractError("unsupported loss_status/coverage_status")
        amount = event["net_loss_cents"]
        if event["loss_status"] == "verified":
            if amount is None:
                raise ContractError("verified loss must have known net_loss_cents; zero is an explicit 0")
            _int(amount, "net_loss_cents")
        elif amount is not None:
            raise ContractError("unverified loss must have net_loss_cents=null")
    return list(events)


def discretize(points: Sequence[tuple[float, float]], step: float) -> dict[int, float]:
    """Spread each (amount, weight) over its two neighbouring grid points so the mean is kept."""
    total = sum(weight for _, weight in points)
    if total <= 0 or step <= 0:
        raise ValueError("weights and step must be positive")
    grid: dict[int, float] = {}
    for amount, weight in points:
        if amount < 0:
            raise ValueError("losses cannot be negative")
        low = int(amount // step)
        upper_share = amount / step - low
        for index, share in ((low, 1 - upper_share), (low + 1, upper_share)):
            if share > 0:
                grid[index] = grid.get(index, 0.0) + share * weight / total
    return grid


def compound_poisson(lam: float, severity: Mapping[int, float], size: int) -> list[float]:
    """Panjer recursion. Values are rescaled as they grow, because exp(-lam) underflows past lam=745."""
    if lam < 0:
        raise ValueError("lam must be nonnegative")
    if severity.get(0, 0.0) >= 1.0:
        raise ValueError("severity must have mass above zero")
    start = -lam * (1.0 - severity.get(0, 0.0))
    terms = sorted((step, lam * step * chance) for step, chance in severity.items() if step > 0)
    widest = terms[-1][0] if terms else 0
    values, scale_at = [1.0], [0]
    rescaled = 0
    for k in range(1, size):
        total = 0.0
        for step, weight in terms:
            if step > k:
                break
            total += weight * values[k - step]
        values.append(total / k)
        scale_at.append(rescaled)
        if values[k] > RESCALE:
            rescaled += 1
            for index in range(max(0, k - widest), k + 1):
                values[index] /= RESCALE
                scale_at[index] = rescaled
    unit = log(RESCALE)
    out = []
    for value, scale in zip(values, scale_at):
        out.append(exp(start + log(value) + scale * unit) if value > 0 else 0.0)
    return out


def add_atoms(distribution: Sequence[float], atoms: Sequence[tuple[float, int]]) -> list[float]:
    """Add an independent amount taking grid value `steps` with probability `chance`; absent mass is zero."""
    missing = 1.0 - sum(chance for chance, _ in atoms)
    if missing < -1e-12:
        raise ValueError("atom probabilities exceed one")
    grown = len(distribution) + max((steps for _, steps in atoms), default=0)
    out = [0.0] * grown
    for chance, steps in [*atoms, (max(missing, 0.0), 0)]:
        if chance > 0:
            for index, mass in enumerate(distribution):
                out[index + steps] += chance * mass
    return out


@dataclass(frozen=True)
class AggregateTerms:
    deductible: float
    share: float
    limit: float

    def paid(self, loss: float) -> float:
        return min(self.limit, self.share * max(loss - self.deductible, 0.0))


@dataclass(frozen=True)
class PremiumBasis:
    risk_loading: float = 0.20
    expense_ratio: float = 0.15
    profit_ratio: float = 0.05
    case_cost: float = 80.0
    fixed_cost: float = 1000.0
    capital_rate: float = 0.08

    def premium(self, expected_paid: float, handling: float, service_fee: float = 0.0) -> float:
        loaded = (1 + self.risk_loading) * expected_paid
        return (loaded + handling + service_fee + self.fixed_cost) / (1 - self.expense_ratio - self.profit_ratio)

    def premium_with_capital(self, expected_paid: float, tail_paid: float, handling: float) -> float:
        loading = max(self.risk_loading * expected_paid, self.capital_rate * max(tail_paid - expected_paid, 0.0))
        return (expected_paid + loading + handling + self.fixed_cost) / (1 - self.expense_ratio - self.profit_ratio)


def tail_stats(outcomes: Sequence[tuple[float, float]]) -> dict[str, float]:
    """Mean, P95, P99 and CTE99 of (value, chance) pairs; an atom at the 99% point is split."""
    ordered = sorted(outcomes)
    total = sum(chance for _, chance in ordered)
    mean, running, p95, p99, tail = 0.0, 0.0, None, None, 0.0
    for value, chance in ordered:
        chance /= total
        mean += value * chance
        before, running = running, running + chance
        if p95 is None and running >= 0.95:
            p95 = value
        if running >= 0.99:
            if p99 is None:
                p99 = value
            tail += value * (running - max(before, 0.99))
    return {"mean": mean, "p95": p95, "p99": p99, "cte99": tail / 0.01}


class AnnualLossModel:
    """One enterprise-year: compound Poisson ordinary losses plus independent batch events.

    `batch_events` is a list of events; each is a list of (annual chance, amount in yuan).
    """

    def __init__(self, lam: float, severity: Sequence[tuple[float, float]], batch_events: Sequence[Sequence[tuple[float, float]]] = (),
                 *, step: float = 50.0, tail_sds: float = 12.0):
        self.lam, self.step = lam, step
        grid = discretize(severity, step)
        self.mean_severity = sum(index * step * chance for index, chance in grid.items())
        second = sum((index * step) ** 2 * chance for index, chance in grid.items())
        size = int((lam * self.mean_severity + tail_sds * sqrt(lam * second) + 40 * max(grid) * step) / step) + 2
        ordinary = compound_poisson(lam, grid, size)
        self.grid, self.ordinary_density = grid, ordinary
        self.batch_atoms = [[(chance, round(amount / step)) for chance, amount in event] for event in batch_events]
        density = ordinary
        for atoms in self.batch_atoms:
            density = add_atoms(density, atoms)
        self.density = density
        self.truncated = 1.0 - sum(density)

    def outcomes(self) -> list[tuple[float, float]]:
        return [(index * self.step, mass) for index, mass in enumerate(self.density) if mass > 0]

    def uninsured(self) -> dict[str, float]:
        return tail_stats(self.outcomes())

    def _claim_points(self, deductible: float) -> tuple[int, int | None]:
        """Grid indices that claim: every index from `full` on, and half of `half`, the one point within half a step of the deductible."""
        full = ceil((deductible + self.step / 2) / self.step - 1e-9)
        half = full - 1
        return full, (half if half >= 0 and deductible - self.step / 2 < half * self.step < deductible + self.step / 2 else None)

    @staticmethod
    def _claim_chance(density: Sequence[float], tail: Sequence[float], shift: int, full: int, half: int | None) -> float:
        """Chance that a year from `density`, moved up by `shift` grid steps, claims; the deductible point counts half."""
        start = full - shift
        if start <= 0:
            return tail[0]
        chance = tail[start] if start < len(tail) else 0.0
        if half is not None and 0 <= half - shift < len(density):
            chance += 0.5 * density[half - shift]
        return chance

    def claim_year_cases(self, deductible: float) -> float:
        """E[K * 1{loss > deductible}]: the events reviewed in claim years, K being the ordinary events plus the batch events of the year.

        For the Poisson count N of ordinary events, E[N g(L)] = lam * E[g(L + X)] with X one more independent severity (the Mecke
        identity), so that part is lam times the claim chance of a year with one more loss added. Each batch event is weighed by its
        own atoms on the distribution of all the other losses. Mass on the deductible counts half, as in `trigger_chance`.
        """
        full, half = self._claim_points(deductible)

        def tails(density: Sequence[float]) -> list[float]:
            out = [0.0] * (len(density) + 1)
            for index in range(len(density) - 1, -1, -1):
                out[index] = out[index + 1] + density[index]
            return out

        tail = tails(self.density)
        cases = self.lam * sum(chance * self._claim_chance(self.density, tail, shift, full, half) for shift, chance in self.grid.items() if chance > 0)
        for position, atoms in enumerate(self.batch_atoms):
            others = self.ordinary_density
            for other, extra in enumerate(self.batch_atoms):
                if other != position:
                    others = add_atoms(others, extra)
            other_tail = tails(others)
            cases += sum(chance * self._claim_chance(others, other_tail, shift, full, half) for chance, shift in atoms if chance > 0)
        return cases

    def evaluate(self, terms: AggregateTerms, basis: PremiumBasis, *, handling: float | None = None, service_fee: float = 0.0) -> dict[str, float]:
        outcomes = self.outcomes()
        paid = [(terms.paid(loss), mass) for loss, mass in outcomes]
        expected = tail_stats(paid)["mean"]
        # Mass sitting exactly on the deductible stands for losses either side of it.
        trigger = sum(mass * (0.5 if abs(loss - terms.deductible) < self.step / 2 else 1.0) for loss, mass in outcomes if loss >= terms.deductible - self.step / 2 and (terms.paid(loss) > 0 or abs(loss - terms.deductible) < self.step / 2))
        if handling is None:
            # Paying under an aggregate deductible means checking every event of a claim year, so the cost is the events of claim
            # years, not the claim chance times the events of an average year: claim years have more events than average.
            handling = basis.case_cost * self.claim_year_cases(terms.deductible)
        premium = basis.premium(expected, handling, service_fee)
        spend = tail_stats([(premium + loss - terms.paid(loss), mass) for loss, mass in outcomes])
        tail_paid = tail_stats(paid)["cte99"]
        capital = basis.premium_with_capital(expected, tail_paid, handling)
        return {**spend, "premium": premium, "expected_paid": expected, "handling": handling, "trigger_chance": trigger,
                "paid_cte99": tail_paid, "loss_ratio": expected / premium if premium else 0.0, "premium_with_capital": capital,
                "cte99_with_capital": spend["cte99"] + capital - premium, "mean_with_capital": spend["mean"] + capital - premium}


def simulate_years(n: int, seed: int, lam: float, severity: Sequence[tuple[float, float]],
                   batch_events: Sequence[Sequence[tuple[float, float]]] = ()) -> list[tuple[list[float], list[float]]]:
    """Sampled years: ordinary losses and batch losses, kept apart so per-event terms can treat them differently."""
    rng = random.Random(seed)
    values = [amount for amount, _ in severity]
    cumulative, running = [], 0.0
    for _, weight in severity:
        running += weight
        cumulative.append(running)
    years = []
    for _ in range(n):
        clock, ordinary = rng.expovariate(lam) if lam > 0 else 2.0, []
        while clock < 1.0:
            ordinary.append(rng.choices(values, cum_weights=cumulative)[0])
            clock += rng.expovariate(lam)
        batch = []
        for event in batch_events:
            draw, seen = rng.random(), 0.0
            for chance, amount in event:
                seen += chance
                if draw < seen:
                    batch.append(amount)
                    break
        years.append((ordinary, batch))
    return years


@dataclass(frozen=True)
class PerEventTerms:
    """The older Core and Plus shape: a deductible on every event, a separate batch sublimit, a yearly cap."""
    deductible: float
    share: float
    occurrence_limit: float
    batch_limit: float
    annual_limit: float

    def paid(self, ordinary: Sequence[float], batch: Sequence[float]) -> float:
        total = sum(min(self.occurrence_limit, self.share * max(loss - self.deductible, 0.0)) for loss in ordinary)
        total += sum(min(self.batch_limit, self.share * max(loss - self.deductible, 0.0)) for loss in batch)
        return min(self.annual_limit, total)


def evaluate_sampled(years: Sequence[tuple[Sequence[float], Sequence[float]]], terms: PerEventTerms, basis: PremiumBasis,
                     *, handling: float, service_fee: float = 0.0) -> dict[str, float]:
    chance = 1.0 / len(years)
    paid = [terms.paid(ordinary, batch) for ordinary, batch in years]
    expected = sum(paid) / len(paid)
    premium = basis.premium(expected, handling, service_fee)
    outcomes = [(premium + sum(ordinary) + sum(batch) - amount, chance) for (ordinary, batch), amount in zip(years, paid)]
    tail_paid = tail_stats([(amount, chance) for amount in paid])["cte99"]
    return {**tail_stats(outcomes), "premium": premium, "expected_paid": expected, "handling": handling, "paid_cte99": tail_paid,
            "trigger_chance": sum(1 for amount in paid if amount > 0) * chance, "loss_ratio": expected / premium if premium else 0.0,
            "premium_with_capital": basis.premium_with_capital(expected, tail_paid, handling)}
