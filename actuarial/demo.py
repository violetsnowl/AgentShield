"""Run: python -m actuarial.demo. All data synthetic engineering examples."""
import json
from pathlib import Path
from .claims import calculate_claim
from .estimate import calculate_quote

ROOT = Path(__file__).resolve().parents[1]


def main():
    contract = json.loads((ROOT / "configs/insurance/research_contract_v0.1.json").read_text(encoding="utf-8"))
    event = {"event_id": "engineering-refund-80-vs-800", "net_loss_cents": 52000,
             "loss_status": "verified", "coverage_status": "covered"}
    claim = calculate_claim(event, contract)
    print("工程算例：应退80元、误退800元、追回200元")
    print("净损失(元):", claim["net_loss_cents"] / 100)
    print("模拟赔款(元):", claim["payout_cents"] / 100)
    print("商户自留(元):", claim["retained_loss_cents"] / 100)
    cases = json.loads((ROOT / "docs/business/engineering_estimate_input_v0.1.json").read_text(encoding="utf-8"))
    kwargs = cases["quote_parameters"]
    quote = calculate_quote(cases["runs"], **kwargs)
    print("B0 每任务平均赔款(分):", quote["methods"]["B0"]["estimated_mean_cents_decimal"])
    print("B1 每任务加权赔款(分):", quote["methods"]["B1"]["estimated_mean_cents_decimal"])
    print("证据状态:", quote["status"], "，真实 Agent 运行次数：0；不可用于商业定价")


if __name__ == "__main__":
    main()
