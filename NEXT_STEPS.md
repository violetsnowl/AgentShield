# 当前停止点与下一步（2026-11-14）

> 本文件是全项目唯一的“状态真源”，只保留当前状态与下一步。上一版原文在 `docs/archive/stop_points_2026-10-16_final.md`。根目录的 `HANDOFF.md`、`TEAM_HANDOFF.md`、`FINAL_STATUS.md` 等是 10 月的旧交接记录，与本文件冲突时以本文件为准。

## 当前状态

- 工作分支 `feature/all-risk-experiment-v2`，跟踪公开远端；有没有未推送的提交，以 `git status` 为准。
- 2026-11-14 检查：后端 `python -m unittest discover -s tests` 共 407 项通过（跳过 3 项），前端 `npm test` 120 项通过，`typecheck` 和 `build` 通过。
- 风险实验：`docs/decisions/RISK_EXPERIMENT_V2.md`。计入统计的真实模型运行 4,326 次，事故 162 起，净损失 ¥86,019.26。各数字的分母见 `docs/validation/BATCH_LEDGER_V0.1.md`。
- 年度精算与合同：`docs/decisions/ACTUARIAL_ANNUAL_V0.2.md` 第 11 节。基础档累计免赔 ¥10 万、增强档 ¥8 万，都赔 90%、年度限额 ¥30 万；保费基础档 ¥3,854–¥9,980，增强档 ¥11,476–¥18,438。
- 外部核查：`docs/decisions/CHECKLIST_RESPONSE_V2.md` 逐条回复了 `衡险v2_核查清单.md` 的 13 项。
- 引擎核对：`docs/validation/ANNUAL_ENGINE_CHECK_V0.1.md`，400 万年独立模拟。
- 商业模式：`docs/business/COMMERCIAL_MODEL_V0.2.md`。首期由厂商和商户付费，保险机构不付费，保险是可选配套；团队已于 2026-11-08 确认这条主线。
- 证据完整性：`python -m experiments.evidence_chain --verify`。
- 哨兵回放：`python -m experiments.sentinel`，线上监测尚未实现。

## 比赛材料（不在仓库内）

比赛材料放在仓库外的上一级目录 `E:\CUFE\竞赛\分子实验室保险\`，没有版本记录。

**当前版本**

| 材料 | 文件 |
| --- | --- |
| 计划书 v2.1（2026-11-08，31 页） | `衡险创业计划书_v2.1.docx` |
| 答辩 PPT v2.2（2026-11-09），主讲 16 页 | `答辩材料\衡险答辩PPT_v2.2.pptx` |
| 答辩 PPT v2.2，备查 12 页 | `答辩材料\衡险答辩_备查页_v2.2.pptx` |
| 口播稿 v2.2 | `答辩材料\衡险答辩口播稿_v2.2.docx` |

- 口播稿另有在线版：https://claude.ai/artifact/9WuGkHyrpgyXbghtgssCm4 。
- 旧版文件都保留未改，已过时。

**PPT 生成与改动**
- 生成源在 `答辩材料\_生成文件_v2\`。重建命令、版式规则、口播稿的三处同步和踩过的坑，都写在该目录的 `README.md`。
- v2.2 只重排了版面，实验和模型数据没有改。主讲页每页只放一个结论和一张主图，底部标出成立条件；明细移到备查页。
- 外部核查清单在 `衡险v2_核查清单.md`，逐条回复见 `docs/decisions/CHECKLIST_RESPONSE_V2.md`。

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

1. 团队抽样复核理赔材料，签收标准答案。这一步只能由成员完成。
2. 试点核实难单占比，用新任务独立验证放权清单。
3. 访谈验证厂商付费意愿和每家厂商能带来的商户数。
4. 答辩 PPT v2.2 按计时器完整排练。口播估算约 11.5 到 12.3 分钟，没算翻页停顿。团队页、指导老师和比赛信息由团队自己补。

## 还没做

- 线上哨兵监测和配置指纹监测。
- 支付渠道对账单这类第三方来源。证据哈希链只能说明记录事后没被改过。
- 规则基线批次的标准答案和网关同源，所以规则基线的 0 信息量很低，第三页不用它定价。
- 工作台的研究情景模式保留了早期 Core、Plus，已标明只作对照。
