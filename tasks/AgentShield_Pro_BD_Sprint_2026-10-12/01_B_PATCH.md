# Astra Codex 本轮任务 01：B 关键阻断补丁

你在**用户现有** AgentShield 仓库中继续施工。用户与舍友暂时视为一个 BD 工作单元，现阶段由用户操作；本轮只修改 B 与必要的契约/测试/文档，不额外重写 C/A/D。

先真实读取当前代码、`README_B.md`、`NEXT_STEPS.md`、`docs/handoff/B_to_C.md`、`docs/decisions/BC_contract_v0.1.md`、V1.1 文档，以及审计包的 `AUDIT_REPORT.md`、`probes.json`、`CODEX_B_NEXT_BATCH.md`。若审计文件未在仓库，明确报告路径缺失，不允许假装读过。确认 Git 状态，保留用户已有改动，不 reset、clean、强行 checkout、不 push、不上传。先在当前 Windows 虚拟环境复跑原 26 项与独立 HTTP 检查，保存原始日志；若命令或依赖有问题先定位而不是伪造通过。

本轮先实现、验证以下内容：

1. F03：修 RequestValidationError 的审计相关信息。数量为 0 等非法业务参数继续 422 且资金不变；认证成功且已独立验证安全的 X-Call-ID/Idempotency-Key 必须进入关联事件；无效、超长或疑似凭据的头不得泄漏、不得被当成有效幂等提交；修正参数后的同键操作仍须遵守原协议。
2. F01：CreateSession、来源枚举、会话快照、ToolEvent、EvidenceBundle 等的契约统一支持 `observed_agent_execution`，同时保持 `scripted_test`、`mock_agent`；这是标签传播能力测试，不是本轮真实模型运行证明。C 后续负责真正 provider/model/request_id/usage 证据，不允许本轮杜撰。
3. F05：实现持久化最小 `submit_human_review`。沿用会话授权、参数与对象范围、幂等和原子事件提交；只保存问题类别、待核实字段与证据引用，不访问 Gold、不自动做出“全知人工”裁决、不修改资金。明确工单与 finish_case(escalated) 的关系。数据库需要迁移时保持原记录可读，不靠删除数据库掩盖兼容问题。
4. F04：与 C 约定 attempted/未知工具/本地拒绝/超时的来源与留痕边界。B 负责可归属的实际 HTTP 及提交事实，不得把未执行的工具记为已执行，不得通过万能路由绕过鉴权。缺 C 真正代码时文档化协议与本机可做的测试，不能代 C 签收。

按已审计的 `CODEX_B_NEXT_BATCH.md` 作为细节规范，遇冲突列明并优先保留金额/权限/交易正确性。更新 `contracts/models.py`、OpenAPI/JSON schema/工具注册表/样例/implementation_status、迁移与 HTTP 手册，新增回归测试；原有正确断言不能删掉或放宽。真实启动服务并执行独立 HTTP 检查、断连后查询/原键恢复、重启恢复，记录命令/退出码/日志。对旧审计用例按新预期更新，而不是把复现旧问题当成功。

**停止点**：提交 B 可运行的补丁检查点；更新 `NEXT_STEPS.md`、`docs/handoff/B_to_C.md`、`docs/decisions/BC_contract_v0.1.md` 或新版本，以及 `artifacts/pro_bd_sprint/01/RESULTS.md`。报告修改文件、实际测试结果、未审字段和需要 A/C 确认的事项。不要自动进行 F02 或 D，等待下一条任务。
