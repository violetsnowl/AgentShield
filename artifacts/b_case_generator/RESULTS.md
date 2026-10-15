# B 案例生成器 B-CP1 / B-CP2 结果

日期：2026-10-14。施工分支：`feature/bd-integration`，基线 `8c4b477`。本轮未切换 main，未执行 commit、push、pull、fetch 或 merge。

## B-CP1

B-CP1 已达到本轮工程验收条件：

- 新增离线确定性生成器 `sandbox/case_generator.py` 与 CLI `scripts/generate_case_candidates.py`。
- 固定输入为 generator_version、rules_version、library_id、seed 和受控配置。同一输入逐字节生成相同 JSON、fixture SHA-256 和 business_initial_hash；不使用当前时间、随机 UUID、Python `hash()`、网络或模型输入。
- `contracts/fixture_ids.py` 是源码固定 allowlist。HTTP 仍只接受枚举 ID，不接受路径、URL、上传、内联 JSON 或运行时登记。
- development fixture schema 增加 v2：商品行可声明会话开始前的历史已退数量、金额及 `pre_session_business_history` 来源。原 `dev-refund-v1/v2` 文件仍是 schema v1，原字节、案例 ID 和业务初态哈希不变。
- 历史退款只进入 canonical/initial snapshot 和期初余额，不生成本次 episode 的 refund、ledger 或 ToolEvent。当前 episode 的可退数量和金额从历史后余额继续计算。
- 七工具、幂等、退款事务、EvidenceBundle schema 3、C 损失核验与 A0 保险公式均未修改；没有迁移 004，也没有重写旧库或历史事实。

## B-CP2

B-CP2 已生成并受控登记 40 个公开候选：

- L0：8 个常规开发候选 + 4 个工程/压力候选。
- L1：24 个常规候选 + 4 个工程/压力候选。
- L1 每个 whole/partial × low/high 类别各 6 个常规候选，其中 3 个 estimate_candidate、3 个 holdout_candidate；同一家族不跨两种划分。
- 覆盖清晰单商品、多商品优惠分摊、相似订单、历史退款、更正确认、信息不足、提示注入、冲突、30 订单边界和不合格拒绝。
- 所有候选均为 `development_only`、`pending_A_C_D_review`、`formal_sample=false`；净损失和保险赔款均为 null。
- 当前分支没有 A1 公共候选补丁或公开 A1 manifest。本库与 A1 的数量和公开业务字段可对接，但属于补充候选，不能宣称替代、审定或冻结 A1 正式任务。

配置规范哈希：`e6ad36ffbe3d6b8206987fe8c7e6960291e74a95f5b61cb65b488ef6608f9cbc`。完整逐案例分类和哈希见 `CASE_MANIFEST.json`。

## 实际联调

真实 loopback B HTTP + 现有 C scripted Mock 已执行 `bcp2-l0-whole-low-01`。运行状态 completed，模拟退款提交 68,731 分，模型费用 0。缺少 A/D Gold obligation spec 时，C 输出 `loss_status=needs_review`、`net_loss_cents=null`；A0 输出 `claim_status=needs_review`、`payout_cents=null`。证据见 `validation/c_mock_e2e_20261014/`。

最终验证：后端 125/125、前端 42/42、B HTTP、生成器、B/OpenAPI、前端契约、C Schema、TypeScript、正式构建均通过；Edge 核心 419 checks、异常/回放 101 checks，以及生成 schema v2 案例专项 21 checks/2 张截图均通过。完整命令和退出码见 `TEST_RESULTS.md` 与 `validation/`。

## 停止点

本轮不调用收费模型或真实支付，不导入私有 Gold，不开发 A/C 正式模块，不执行正式留出实验。B-CP1 和 B-CP2 均完成；下一步由 A 审业务 Gold、C 冻结运行清单并执行经批准的实验、D 仅在已审结果到位后展示正式结果。
