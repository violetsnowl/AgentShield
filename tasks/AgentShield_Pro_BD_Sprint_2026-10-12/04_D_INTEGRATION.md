# Astra Codex 本轮任务 04：D 真实数据整合、空状态与交接

只有在 01—03 的核心测试通过后继续。目标不是重做页面，而是把 D 的工作台做成**一名新开发者能够复现**的系统，并为日后 A/C 数据接入做好明确、可测的适配边界。

本轮完成：
- 实测案例/运行/事件/交易/账本关联跳转，开发来源标签与状态完整展示，列表筛选和错误状态可读；不能通过静态数组伪装后台数据。
- `LossResult`/`QuoteResult` 的 TypeScript 类型/版本化适配器、空状态、not_fitted/insufficient_evidence/partial/out_of_scope 视觉处理，保持 `commercial_quote=false` 的文字提示；真正数据缺席时不作假值，不调用权威计算。
- 如 B 已有获得授权的任务触发入口则按契约集成；C 尚未交付真实 Agent 运行器，不得创建假“运行成功”按钮。如要做 scripted 调试操作，必须与真实模型执行完全分离、明确显示。
- 前端与服务端鉴权/只读桥接安全审查；敏感值扫描；断网已存回放的最小能力或不满足时的明确缺口。构建、类型检查、实际端到端 HTTP/界面检查；退出码与路径保存。
- 为 A/C 提供接口需要的最小字段清单和样例。输出 `docs/handoff/BD_to_A_C.md`、`artifacts/pro_bd_sprint/04/RESULTS.md`，更新 `README_B.md`、`frontend/README.md`、`NEXT_STEPS.md`。保留版本可回退点。

不扩正式实验、不调用付费模型、不伪造保险结果、不改 Gold。完成后停止，不进行 L2 美化。
