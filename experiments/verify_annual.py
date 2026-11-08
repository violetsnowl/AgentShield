"""Independent Monte Carlo check of the annual engine (actuarial/annual.py).

  PYTHONPATH=. python -m experiments.verify_annual            4,000,000 years, writes docs/validation
  PYTHONPATH=. python -m experiments.verify_annual --years 400000 --no-write

The engine is exact only for its own discretised model. This script samples the undiscretised model
with numpy and compares the two. It never calls the Panjer recursion to produce the sample.
Ordinary events: N ~ Poisson(lam), each amount drawn from the real severity points, no 50-yuan grid.
Batch events: each event takes at most one of its atoms per year, independently of the others.
The difference between the engine and the sample is then sampling error plus grid error. The grid
error is estimated by running the same engine on a finer grid; it is listed in its own column.

Needs numpy, which the project virtualenv does not have; run it with the system python.
Nothing here is a commercial quote.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from math import sqrt
import platform
import subprocess
import sys
import time
from typing import Any

try:
    import numpy as np
except ImportError:  # the module stays importable so the tests can skip cleanly
    np = None

from actuarial.annual import AggregateTerms, AnnualLossModel, PremiumBasis, tail_stats
from experiments.annual_report import ROOT, Scenario, batch_events, load_inputs, model_for, pricing_frequency, severity_points, terms_of

SEED = 20261108
YEARS = 4_000_000
BATCHES = 40
FINE_STEP = 10.0
Z_LIMIT = 3.0
OUT_DIR = ROOT / "docs/validation"
JSON_NAME = "annual_engine_check_v0.1.json"
MD_NAME = "ANNUAL_ENGINE_CHECK_V0.1.md"
HASHED = ("actuarial/annual.py", "experiments/annual_report.py", "configs/insurance/annual_evidence_v0.2.json",
          "configs/insurance/annual_assumptions_v0.2.json")

CELL_NAME = {"A": "A 类", "B": "B 类", "C": "C 类", "D": "D 类"}
CASES = "E[K·1{赔款>0}]"


def require_numpy() -> None:
    if np is None:
        print("缺少 numpy：这个核对需要 numpy。.venv 里没有，请改用装了 numpy 的系统 python：\n"
              "  PYTHONIOENCODING=utf-8 PYTHONPATH=. python -m experiments.verify_annual", file=sys.stderr)
        raise SystemExit(2)


# ---- sampling -------------------------------------------------------------------------------------------------

def sample_cell(seed: Any, lam: float, severity: list[tuple[float, float]], events: list[list[tuple[float, float]]],
                years: int, batches: int, *, ordinary: str = "multinomial") -> tuple[Any, Any]:
    """Yearly total loss L and event count K. Memory is bounded by one batch of years at a time.

    `ordinary="per_event"` draws every accident on its own. `"multinomial"` draws N, then splits the N
    accidents over the distinct amounts; the law is the same, and it is the only way to do lam=1373 for
    millions of years in minutes. Both use the real amounts, never the grid.
    """
    if years % batches:
        raise ValueError("years must be a multiple of batches")
    size = years // batches
    rng = np.random.default_rng(seed)
    values = np.array([amount for amount, _ in severity], dtype=float)
    weights = np.array([weight for _, weight in severity], dtype=float)
    probs = weights / weights.sum()
    total_loss, total_count = np.empty(years), np.empty(years, dtype=np.int64)
    for batch in range(batches):
        count = rng.poisson(lam, size)
        if ordinary == "multinomial":
            loss = rng.multinomial(count, probs) @ values
        elif ordinary == "per_event":
            drawn = values[rng.choice(len(values), size=int(count.sum()), p=probs)]
            loss = np.bincount(np.repeat(np.arange(size), count), weights=drawn, minlength=size)
        else:
            raise ValueError("ordinary must be multinomial or per_event")
        for event in events:
            cumulative = np.cumsum([chance for chance, _ in event])
            amounts = np.array([amount for _, amount in event] + [0.0])
            slot = np.searchsorted(cumulative, rng.random(size), side="right")  # draw < cumulative, as simulate_years
            hit = slot < len(event)
            loss = loss + amounts[slot]
            count = count + hit
        window = slice(batch * size, (batch + 1) * size)
        total_loss[window], total_count[window] = loss, count
    return total_loss, total_count


# ---- statistics -----------------------------------------------------------------------------------------------

def p99_cte99(values: Any) -> tuple[float, float]:
    """The same definitions as tail_stats on equal-chance outcomes: P99 is the first value with cumulative >= 99%,
    and CTE99 averages the worst 1%, splitting the value that straddles the 99% point."""
    ordered = np.sort(values)
    n = len(ordered)
    p99 = float(ordered[-(-99 * n // 100) - 1])
    tail = n / 100
    whole = int(tail + 1e-9)
    part = tail - whole
    total = float(ordered[n - whole:].sum()) + (part * float(ordered[n - whole - 1]) if part > 1e-9 else 0.0)
    return p99, total / tail


def estimate(values: Any, batches: int, kind: str) -> tuple[float, float]:
    """Estimate and its standard error. Means use the yearly spread; P99 and CTE99 use the spread of batch estimates."""
    n = len(values)
    if kind == "mean":
        return float(values.mean()), float(values.std(ddof=1) / sqrt(n))
    pick = 0 if kind == "p99" else 1
    each = np.array([p99_cte99(chunk)[pick] for chunk in np.split(values, batches)])
    return p99_cte99(values)[pick], float(each.std(ddof=1) / sqrt(batches))


def item(cell: str, group: str, metric: str, kind: str, engine: float, sim: float, se: float, fine: float | None) -> dict[str, Any]:
    diff = engine - sim
    z = diff / se if se > 0 else (0.0 if diff == 0 else float("inf"))
    row = {"cell": cell, "group": group, "metric": metric, "unit": kind, "engine": engine, "sim": sim, "diff": diff, "se": se, "z": z,
           "within_3se": abs(z) <= Z_LIMIT}
    if fine is not None:
        gap = engine - fine
        after = (fine - sim) / se if se > 0 else 0.0
        row.update(engine_fine_grid=fine, grid_gap=gap, z_after_grid=after, within_3se_after_grid=abs(after) <= Z_LIMIT)
    return row


# ---- one cell -------------------------------------------------------------------------------------------------

def spend_stats(model: AnnualLossModel, terms: AggregateTerms, premium: float) -> dict[str, float]:
    return tail_stats([(premium + loss - terms.paid(loss), mass) for loss, mass in model.outcomes()])


def check_cell(evidence: dict[str, Any], assumptions: dict[str, Any], tier_key: str, monitored: bool, contracts: dict[str, AggregateTerms],
               years: int, batches: int, seed: Any, *, fine_step: float | None = FINE_STEP, ordinary: str = "multinomial") -> dict[str, Any]:
    scene, basis = Scenario.from_assumptions(assumptions), PremiumBasis(**assumptions["premium"])
    tier = evidence["tiers"][tier_key]
    cell = f"{CELL_NAME[tier_key]}{'有' if monitored else '无'}监测"
    model, lam = model_for(evidence, tier, scene, monitored)
    rate = pricing_frequency(tier, scene.gate_leak)
    severity, events = severity_points(evidence, scene.severity_scale), batch_events(evidence, tier, scene, monitored, rate)
    fine = None
    if fine_step:
        fine = AnnualLossModel(lam, severity, events, step=fine_step)

    started = time.perf_counter()
    loss, count = sample_cell(seed, lam, severity, events, years, batches, ordinary=ordinary)
    sampled_seconds = time.perf_counter() - started

    bare, bare_fine = model.uninsured(), fine.uninsured() if fine else None
    items = []
    for kind, key, label in (("mean", "mean", "不投保均值"), ("p99", "p99", "不投保P99"), ("cte99", "cte99", "不投保CTE99")):
        value, se = estimate(loss, batches, kind)
        items.append(item(cell, "不投保", label, "yuan", bare[key], value, se, bare_fine[key] if fine else None))

    for name, terms in contracts.items():
        row = model.evaluate(terms, basis)
        row_fine = fine.evaluate(terms, basis) if fine else None
        premium = row["premium"]
        spend_fine = spend_stats(fine, terms, premium) if fine else None
        paid = np.minimum(terms.limit, terms.share * np.maximum(loss - terms.deductible, 0.0))
        claim = paid > 0
        mean_paid, se_paid = estimate(paid, batches, "mean")
        chance, se_chance = estimate(claim.astype(float), batches, "mean")
        spend = premium + loss - paid
        mean_spend, se_mean_spend = estimate(spend, batches, "mean")
        cte_spend, se_cte_spend = estimate(spend, batches, "cte99")
        cases, se_cases = estimate(count * claim, batches, "mean")
        group = f"投保（{name}）"
        items += [item(cell, group, "期望赔款", "yuan", row["expected_paid"], mean_paid, se_paid, row_fine["expected_paid"] if fine else None),
                  item(cell, group, "有赔款年份概率", "prob", row["trigger_chance"], chance, se_chance, row_fine["trigger_chance"] if fine else None),
                  item(cell, group, "投保后年支出均值", "yuan", row["mean"], mean_spend, se_mean_spend, spend_fine["mean"] if fine else None),
                  item(cell, group, "投保后年支出CTE99", "yuan", row["cte99"], cte_spend, se_cte_spend, spend_fine["cte99"] if fine else None),
                  item(cell, group, CASES, "count", row["handling"] / basis.case_cost, cases, se_cases, row_fine["handling"] / basis.case_cost if fine else None)]
        for entry in items[-5:]:
            entry["contract"], entry["premium_used"] = name, premium
    return {"cell": cell, "tier": tier_key, "monitored": monitored, "lambda": lam, "frequency": rate, "batch_events": [len(e) for e in events],
            "contracts": {name: {"deductible": t.deductible, "share": t.share, "limit": t.limit} for name, t in contracts.items()},
            "engine_grid_step": model.step, "engine_truncated_mass": model.truncated, "fine_grid_step": fine_step,
            "sample_seconds": sampled_seconds, "sample_mean_events_per_year": float(count.mean()), "items": items}


def cell_plan(assumptions: dict[str, Any]) -> list[tuple[str, bool, dict[str, AggregateTerms]]]:
    base, enhanced = terms_of(assumptions["base_contract"]), terms_of(assumptions["enhanced_contract"])
    plan = []
    for key in ("A", "B", "C", "D"):
        for monitored in (False, True):
            contracts = {}
            if key == "B":
                contracts = {"基础档": base} if monitored else {"基础档": base, "增强档": enhanced}
            plan.append((key, monitored, contracts))
    return plan


def run(years: int = YEARS, batches: int = BATCHES, seed: int = SEED, *, fine_step: float | None = FINE_STEP, ordinary: str = "multinomial",
        progress: bool = False) -> dict[str, Any]:
    require_numpy()
    evidence, assumptions = load_inputs()
    plan = cell_plan(assumptions)
    seeds = np.random.SeedSequence(seed).spawn(len(plan))  # one stream per cell, fixed by cell order
    started = time.perf_counter()
    cells = []
    for (key, monitored, contracts), stream in zip(plan, seeds):
        cells.append(check_cell(evidence, assumptions, key, monitored, contracts, years, batches, stream, fine_step=fine_step, ordinary=ordinary))
        if progress:
            print(f"{cells[-1]['cell']}: {cells[-1]['sample_seconds']:.1f}s", flush=True)
    items = [entry for cell in cells for entry in cell["items"]]
    return {"schema": "AgentShield.annual_engine_check.v0.1", "commercial_quote": False,
            "run": {"seed": seed, "seed_method": "numpy SeedSequence(seed).spawn(8), one stream per cell in cell order", "years": years, "batches": batches,
                    "years_per_batch": years // batches, "ordinary_draw": ordinary, "z_limit": Z_LIMIT, "fine_grid_step": fine_step,
                    "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
                    "git_head": git(["rev-parse", "HEAD"]), "git_branch": git(["branch", "--show-current"]),
                    "git_changes": git(["status", "--porcelain", "--", "actuarial", "experiments", "configs"]).splitlines(),
                    "sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in HASHED},
                    "runtime_seconds": time.perf_counter() - started},
            "cells": cells,
            "summary": {"items": len(items), "within_3se": sum(e["within_3se"] for e in items),
                        "outside_3se": [f"{e['cell']}·{e['metric']}" if "contract" not in e else f"{e['cell']}·{e['contract']}·{e['metric']}" for e in items if not e["within_3se"]],
                        "outside_3se_after_grid": [f"{e['cell']}·{e['metric']}" if "contract" not in e else f"{e['cell']}·{e['contract']}·{e['metric']}"
                                                   for e in items if "within_3se_after_grid" in e and not e["within_3se_after_grid"]]}}


def git(args: list[str]) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
        return done.stdout.strip() if done.returncode == 0 else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


# ---- report ---------------------------------------------------------------------------------------------------

def number(value: float, unit: str) -> str:
    if unit == "prob":
        return f"{value:.6f}"
    if unit == "count":
        return f"{value:.4f}"
    return f"{value:,.2f}"


def signed(value: float, unit: str) -> str:
    return ("+" if value >= 0 else "-") + number(abs(value), unit)


def table(rows: list[dict[str, Any]]) -> list[str]:
    out = ["| 格子 | 项目 | 引擎 | 模拟 | 差（引擎−模拟） | 标准误 | 差/标准误 | 3 倍内 | 格点差 | 扣格点差后 差/标准误 | 3 倍内 |",
           "|---|---|---:|---:|---:|---:|---:|:--:|---:|---:|:--:|"]
    for e in rows:
        unit = e["unit"]
        label = e["cell"] + (f"·{e['contract']}" if "contract" in e else "")
        out.append(f"| {label} | {e['metric']} | {number(e['engine'], unit)} | {number(e['sim'], unit)} | {signed(e['diff'], unit)} | {number(e['se'], unit)} | "
                   f"{e['z']:+.2f} | {'是' if e['within_3se'] else '**否**'} | {signed(e['grid_gap'], unit)} | {e['z_after_grid']:+.2f} | "
                   f"{'是' if e['within_3se_after_grid'] else '**否**'} |")
    return out


def markdown(result: dict[str, Any]) -> str:
    run_info, summary = result["run"], result["summary"]
    items = [entry for cell in result["cells"] for entry in cell["items"]]
    bare = [e for e in items if e["group"] == "不投保"]
    insured = [e for e in items if e["group"] != "不投保" and e["metric"] != CASES]
    cases = [e for e in items if e["metric"] == CASES]
    years, seed = run_info["years"], run_info["seed"]
    outside = "、".join(summary["outside_3se"]) or "无"
    outside_after = "、".join(summary["outside_3se_after_grid"]) or "无"
    lines = [
        "# 年度引擎独立蒙特卡洛核对 V0.1", "",
        "本文件由 `experiments/verify_annual.py` 生成。数字以同名 JSON 为准。", "",
        "## 结论", "",
        f"- 共比较 {summary['items']} 项。差值在 3 个标准误以内的有 {summary['within_3se']} 项。",
        f"- 超过 3 个标准误的项：{outside}。",
        f"- 扣掉格点差（引擎 {result['cells'][0]['engine_grid_step']:g} 元格点对 {run_info['fine_grid_step']:g} 元格点）后，仍超过 3 个标准误的项：{outside_after}。",
        f"- 模拟 {years:,} 个年度，种子 {seed}，用时 {run_info['runtime_seconds']:.0f} 秒。", "",
        "## 方法", "",
        "引擎用 50 元格点和 Panjer 递推算年度损失分布。核对不用这条路。", "",
        "- 普通事故数 N 取泊松分布，均值 λ。",
        "- 每起事故的金额，直接从 69 个真实严重度金额里按权重抽。不做格点。",
        "- 抽 N 之后，把 N 起事故按权重分到各个金额上（多项分布）。这和逐起独立抽同分布。"
        "D 类 λ 约 1373，逐起抽要上百亿次，所以用多项分布。脚本留了 `ordinary=\"per_event\"` 逐起抽的写法，可对照。",
        "- 每个批量事故按自己的原子独立抽。一年最多发生一次。没抽中任何原子，就没有这个事故。",
        "- 年度总损失 L = 普通损失 + 批量损失。",
        "- 8 个格子（A、B、C、D 各分无监测、有监测）各用独立的随机流。流由 `SeedSequence(种子).spawn(8)` 按格子顺序生成。",
        f"- 每个格子分 {run_info['batches']} 批，每批 {run_info['years_per_batch']:,} 年，分批生成，内存只占一批。", "",
        "标准误怎么算：", "",
        "- 均值、概率：用逐年样本的标准差除以根号年数。",
        f"- P99、CTE99：每批各算一次，取 {run_info['batches']} 个批估计值的标准差，除以根号批数。",
        "- 差值 = 引擎值 − 模拟值。差值的绝对值不超过 3 个标准误，记为“3 倍内”。", "",
        "投保后年支出 = 引擎保费 + L − 赔款。保费直接取引擎 `evaluate` 给出的值，两边用同一个数。", "",
        "## CTE99 在离散分布上的定义", "",
        "分布是离散的，99% 点上往往有一块概率质量。`tail_stats` 的做法：",
        "",
        "- P99 取累计概率第一次达到 99% 的那个值。",
        "- CTE99 是最差 1% 概率上的平均损失。99% 点上的质量只取落在最差 1% 里的那一部分，其余留在 99% 之内。",
        "",
        f"模拟侧每个年度概率相同，各为 1/n。排序后，P99 取第 ceil(0.99n) 个值。CTE99 取最大的 n/100 个值的平均。"
        "n/100 不是整数时，边界上的那个值按比例拆分。这和 `tail_stats` 一致。", "",
        "## 误差表", "",
        "单位是元，概率和次数除外。“格点差”是引擎 50 元格点值减 10 元格点值。它是离散化造成的系统差，不是抽样误差。"
        "“扣格点差后”是 10 元格点引擎值与模拟值之差，除以同一个标准误。", "",
        "### 不投保", ""] + table(bare) + ["", "### B 类投保", ""] + table(insured) + [
        "", f"### 理赔次数 {CASES}", "",
        "K = 当年普通事故数 + 发生的批量事故数。引擎侧取 `evaluate(terms, basis)[\"handling\"] / case_cost`。"
        "处理费口径若改过，这一项应与模拟值相符；没改，就对不上。表里如实列出，核对脚本不改引擎。", ""] + table(cases) + [
        "", "## 说明", "",
        "- “精确”只针对离散化后的模型。引擎在 50 元格点上做保均值离散，批量金额四舍五入到格点，时延用四点近似。这三处各有误差，不在“精确”之内。",
        "- 本核对的模拟侧不做格点，能看出前两处。时延四点近似是模型本身的设定，模拟侧用同样的四点，所以这一处看不出来。",
        f"- {years:,} 年是模拟的年度数，不是业务经验。参数是研究假设，不是真实经营数据。",
        f"- 3 倍标准误只约束抽样误差。全表 {summary['items']} 项，逐项检验。若引擎和模拟都对，偶尔有一项落在 3 倍外并不奇怪。要看是否成片、是否有方向。",
        "", "## 复算命令", "", "```", "PYTHONIOENCODING=utf-8 PYTHONPATH=. python -m experiments.verify_annual", "```", "",
        "需要装了 numpy 的 python。项目的 `.venv` 没有 numpy，用系统 `python`。同一份代码、同一个种子、同一个 numpy 版本，结果应当相同。换 numpy 版本或机器，末位可能不同。", "",
        "## 运行记录", "",
        f"- 种子：{seed}",
        f"- 模拟年数：{years:,}（{run_info['batches']} 批）",
        f"- 运行时间：{run_info['runtime_seconds']:.1f} 秒",
        f"- Python {run_info['python']}，numpy {run_info['numpy']}",
        f"- git 分支 {run_info['git_branch']}，HEAD {run_info['git_head']}",
        f"- 运行时工作区有改动的文件（actuarial、experiments、configs）：{'、'.join(line.strip() for line in run_info['git_changes']) or '无'}",
        "- 各输入文件的 SHA-256 见 JSON。", "",
        "各格子 λ 与用时：", "", "| 格子 | λ | 批量事故原子数 | 用时（秒） |", "|---|---:|---|---:|"]
    for cell in result["cells"]:
        lines.append(f"| {cell['cell']} | {cell['lambda']:.3f} | {'+'.join(str(n) for n in cell['batch_events'])} | {cell['sample_seconds']:.1f} |")
    return "\n".join(lines) + "\n"


def write(result: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / JSON_NAME, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    with open(OUT_DIR / MD_NAME, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(markdown(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=YEARS)
    parser.add_argument("--batches", type=int, default=BATCHES)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--ordinary", choices=("multinomial", "per_event"), default="multinomial")
    parser.add_argument("--no-write", action="store_true", help="print the summary only; do not write docs/validation")
    args = parser.parse_args()
    require_numpy()
    outcome = run(args.years, args.batches, args.seed, ordinary=args.ordinary, progress=True)
    if not args.no_write:
        write(outcome)
    print(json.dumps({**outcome["summary"], "runtime_seconds": outcome["run"]["runtime_seconds"]}, ensure_ascii=False, indent=1))
