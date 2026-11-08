"""Three-year budget for the plan's old pricing and for the pay-for-testing model.

  python -m experiments.finance_model

Every price, conversion and headcount-style number here is a planning assumption, not a result.
The old case exists so a test can pin it to the figures printed in the plan; the new case changes
who pays, which lines exist and the monitoring cost, and leaves the funnel and fixed costs alone.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any

from experiments.annual_report import OUTPUT as ANNUAL_RESULTS
from experiments.claim_pack import ROOT

OUTPUT = ROOT / "docs/business/finance_results_v0.2.json"
WAN = 10000.0


@dataclass(frozen=True)
class Plan:
    entries: tuple[int, ...] = (6, 9, 15)              # paid first engagements each year
    conversions: tuple[int, ...] = (2, 3, 5)           # of those, how many become annual accounts
    renewal: float = 0.90
    merchants_per_account: float = 50.0
    entry_price: float = 30000.0
    entry_cost: float = 20000.0
    conversion_price: float = 30000.0                  # paid on top of the first engagement
    conversion_cost: float = 20000.0
    account_price: float = 120000.0
    account_cost: float = 36000.0
    merchant_price: float = 4800.0
    merchant_cost: float = 2000.0
    fixed_costs: tuple[float, ...] = (840000.0, 1100000.0, 1500000.0)
    opening_cash: float = 1800000.0
    setup_cash: float = 150000.0
    receivable_share: float = 0.20


OLD = Plan()
# Accounts are now Agent vendors, merchants pay for monitoring themselves, and insurers pay nothing in the base case.
# Monitoring cost: the plan's 2,000, less its 100 of replays, plus the dearest sentinel model bill of 1,186.
NEW = replace(OLD, merchants_per_account=20.0, merchant_price=7200.0, merchant_cost=3086.0)
# A look past the three-year budget: the third year repeats and fixed costs keep growing.
FOURTH_YEAR = replace(NEW, entries=(6, 9, 15, 15), conversions=(2, 3, 5, 5), fixed_costs=(840000.0, 1100000.0, 1500000.0, 1700000.0))


def account_years(plan: Plan) -> tuple[list[float], list[float]]:
    """New accounts arrive evenly through the year; losses to renewal happen at the start of it."""
    closing, effective, open_accounts = [], [], 0.0
    for added in plan.conversions:
        kept = open_accounts * plan.renewal
        effective.append(kept + added * 0.5)
        open_accounts = kept + added
        closing.append(open_accounts)
    return effective, closing


def budget(plan: Plan) -> list[dict[str, float]]:
    effective, closing = account_years(plan)
    rows, cash, previous_receivable = [], plan.opening_cash - plan.setup_cash, 0.0
    for year in range(len(plan.entries)):
        entries, conversions, accounts = plan.entries[year], plan.conversions[year], effective[year]
        merchants = accounts * plan.merchants_per_account
        lines = {"entry": entries * plan.entry_price, "conversion": conversions * plan.conversion_price,
                 "account": accounts * plan.account_price, "merchant": merchants * plan.merchant_price}
        direct = (entries * plan.entry_cost + conversions * plan.conversion_cost + accounts * plan.account_cost + merchants * plan.merchant_cost)
        revenue = sum(lines.values())
        surplus = revenue - direct - plan.fixed_costs[year]
        receivable = revenue * plan.receivable_share
        cash += surplus - (receivable - previous_receivable)
        previous_receivable = receivable
        rows.append({"year": year + 1, "accounts": accounts, "accounts_closing": closing[year], "merchants": merchants, "revenue": revenue, **{f"revenue_{key}": value for key, value in lines.items()},
                     "direct_cost": direct, "fixed_cost": plan.fixed_costs[year], "surplus": surplus, "closing_cash": cash})
    return rows


def merchants_to_break_even(plan: Plan, year: int = 3) -> float:
    """Merchants per account at which that year's surplus reaches zero, all else equal."""
    row = budget(plan)[year - 1]
    margin = (plan.merchant_price - plan.merchant_cost) * row["accounts"]
    return plan.merchants_per_account - row["surplus"] / margin


def merchants_for_flat_cash(plan: Plan, year: int = 3) -> float:
    """Merchants per account at which cash stops falling that year; receivables keep growing, so this sits above break-even."""
    low, high = plan.merchants_per_account, 500.0
    for _ in range(60):
        middle = (low + high) / 2
        rows = budget(replace(plan, merchants_per_account=middle))
        if rows[year - 1]["closing_cash"] >= rows[year - 2]["closing_cash"]:
            high = middle
        else:
            low = middle
    return high


def price_to_break_even(plan: Plan, field: str, year: int = 3) -> float:
    """The one price that brings that year to zero, all else equal."""
    row = budget(plan)[year - 1]
    units = row["merchants"] if field == "merchant_price" else row["accounts"]
    return getattr(plan, field) - row["surplus"] / units


def scenarios() -> dict[str, list[dict[str, float]]]:
    return {"基准（每家厂商 20 家商户）": budget(NEW),
            "每家厂商 10 家商户": budget(replace(NEW, merchants_per_account=10.0)),
            "每家厂商 50 家商户": budget(replace(NEW, merchants_per_account=50.0)),
            "续约率 80%": budget(replace(NEW, renewal=0.80)),
            "新增账户减半，测评联动": budget(replace(NEW, entries=(3, 4.5, 7.5), conversions=(1, 1.5, 2.5))),
            "监测价 4,800 元": budget(replace(NEW, merchant_price=4800.0)),
            "应收占收入 40%": budget(replace(NEW, receivable_share=0.40))}


def market() -> list[dict[str, float]]:
    """Standard-merchant equivalents: online retail of physical goods divided by the sales behind one standard merchant.

    This is a conversion, not a count of customers and not an upper bound: a higher real refund rate per sale gives more equivalents.
    """
    # The same merchants pay for monitoring, so they buy cover at the monitored premium.
    results = json.loads(ANNUAL_RESULTS.read_text(encoding="utf-8"))
    watched = next(row["insured"] for row in results["tiers"] if row["tier"] == "B" and row["monitored"])
    physical_goods_retail = 13.09e12  # refunds of goods; the 15.97 trillion total includes services
    # Paid amount of the 100,000 orders in synthetic_merchant_v1.sqlite3 (yuan), scaled from its 6,105 agent-handled refund requests
    # to 100,000 tasks a year: one refund task per about 16,773 yuan of sales. Both figures come from the simulated population.
    standard_merchant_sales = 102400661.08 * (100000 / 6105)
    equivalents = physical_goods_retail / standard_merchant_sales
    out = []
    for adoption in (0.10, 0.30):
        merchants = equivalents * adoption
        vendors = merchants / NEW.merchants_per_account
        out.append({"adoption": adoption, "merchant_equivalents": equivalents, "merchants": merchants, "monitoring": merchants * NEW.merchant_price,
                    "vendors": vendors, "vendor_plans": vendors * NEW.account_price,
                    "premium_low": merchants * watched["premium"], "premium_high": merchants * watched["premium_with_capital"]})
    return out


def build() -> dict[str, Any]:
    return {"schema": "AgentShield.finance_results.v0.2", "nature": "规划假设，不是预测或已实现结果", "old": budget(OLD), "new": budget(NEW), "fourth_year": budget(FOURTH_YEAR)[3], "scenarios": scenarios(),
            "break_even_merchants_year3": merchants_to_break_even(NEW), "flat_cash_merchants_year3": merchants_for_flat_cash(NEW),
            "break_even_at_4800": merchants_to_break_even(replace(NEW, merchant_price=4800.0)), "break_even_monitoring_price": price_to_break_even(NEW, "merchant_price"),
            "break_even_account_price": price_to_break_even(NEW, "account_price"), "market": market()}


if __name__ == "__main__":
    results = build()
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, rows in {"旧模式": results["old"], **results["scenarios"]}.items():
        print(name, [(round(row["revenue"] / WAN, 1), round(row["surplus"] / WAN, 1), round(row["closing_cash"] / WAN, 1)) for row in rows])
    print("第三年打平需要每账户商户数", round(results["break_even_merchants_year3"], 1))
    print(results["market"])
