# 当前停止点与下一步（2026-11-08）

> 本文件是全项目唯一的“状态真源”，只保留当前状态与下一步。上一版原文在 `docs/archive/stop_points_2026-10-16_final.md`。

## 当前状态

- 工作分支 `feature/all-risk-experiment-v2`，已推送到公开远端。
- 风险实验：`docs/decisions/RISK_EXPERIMENT_V2.md`。计入统计的真实模型运行 4,326 次，事故 162 起，净损失 ¥86,019.26。各数字的分母见 `docs/validation/BATCH_LEDGER_V0.1.md`。
- 年度精算与合同：`docs/decisions/ACTUARIAL_ANNUAL_V0.2.md` 第 11 节。基础档累计免赔 ¥10 万、增强档 ¥8 万，都赔 90%、年度限额 ¥30 万；保费基础档 ¥3,854–¥9,980，增强档 ¥11,476–¥18,438。
- 外部核查：`docs/decisions/CHECKLIST_RESPONSE_V2.md` 逐条回复了 `衡险v2_核查清单.md` 的 13 项。
- 引擎核对：`docs/validation/ANNUAL_ENGINE_CHECK_V0.1.md`，400 万年独立模拟。
- 商业模式：`docs/business/COMMERCIAL_MODEL_V0.2.md`。首期由厂商和商户付费，保险机构不付费；这是商业选择，待团队确认。
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
python -m experiments.batch_ledger
python -m experiments.verify_annual   # 需要 numpy
```

## 下一步

1. 团队确认商业主线：厂商和商户付费、保险是可选配套。
2. 团队抽样复核理赔材料，签收标准答案。这一步只能由成员完成。
3. 试点核实难单占比，用新任务独立验证放权清单。

## 还没做

- 线上哨兵监测和配置指纹监测。
- 支付渠道对账单这类第三方来源。证据哈希链只能说明记录事后没被改过。
- 规则基线批次的标准答案和网关同源，所以规则基线的 0 信息量很低，第三页不用它定价。
- 工作台的研究情景模式保留了早期 Core、Plus，已标明只作对照。
