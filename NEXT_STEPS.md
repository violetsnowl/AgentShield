# 当前停止点与下一步（2026-11-07）

> 本文件是全项目唯一的“状态真源”，只保留当前状态与下一步。上一版原文在 `docs/archive/stop_points_2026-10-16_final.md`。

## 当前状态

- 工作分支 `feature/all-risk-experiment-v2`。公开远端停在 `3b9e240`，第二阶段之后的改动都还在本地。
- 风险实验：`docs/decisions/RISK_EXPERIMENT_V2.md`。真实模型有效运行 4,326 次，事故 162 起，净损失 ¥86,019.26。
- 年度精算与合同：`docs/decisions/ACTUARIAL_ANNUAL_V0.2.md` 第 10 节。基础档累计免赔 ¥10 万、增强档 ¥8 万，都赔 90%、年度限额 ¥30 万。
- 商业模式：`docs/business/COMMERCIAL_MODEL_V0.2.md`。厂商和商户付费，保险机构基准不付费。
- 证据完整性：`python -m experiments.evidence_chain --verify`。
- 哨兵回放：`python -m experiments.sentinel`，线上监测尚未实现。

## 复现

```bash
python -m experiments.annual_calibration
python -m experiments.annual_report
python -m experiments.finance_model
python -m experiments.sentinel
python -m experiments.authorization_list
python -m experiments.evidence_chain
```

## 下一步

1. 更新答辩 PPT 和口播稿，按计划书新稿。
2. 团队抽样复核理赔材料，签收基准。这一步只能由成员完成。

## 还没做

- 线上哨兵监测和配置指纹监测。
- 支付渠道对账单这类第三方来源。证据哈希链只能说明记录事后没被改过。
- 规则基线批次的基准和网关同源，所以规则基线的 0 信息量很低，第三页不用它定价。
- 工作台的研究情景模式保留了早期 Core、Plus，已标明只作对照。
