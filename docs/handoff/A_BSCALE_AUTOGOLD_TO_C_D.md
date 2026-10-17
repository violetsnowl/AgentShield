# A → C/D：B-SCALE 动态模拟授权自动 Gold（开发候选）

- 基线：`feature/research-risk-contracts`，`14fa67bd9226086b4963bdbe2fe6b10fb76dfaf9`（2026-10-17）。
- 生成器：`scripts/a_bscale_auto_gold.py`；批量接口：`scripts/a_bscale_auto_gold_batch.py`。
- 保证只读 **事前** `sandbox.bscale_authorization.load_dynamic_fixture(...)` 输出，不读取 DeepSeek 轨迹、B 提交退款、C LossResult。
- 输出 obligation spec 必须 **单独私下交给 C**，只在 B/C 结束实际 episode 后作离线核验；禁止进 Agent、前端、公共仓库、prompt。
- `review_status=A_auto_generated_D_not_signed`；自动生成候选可用于开发核验，不冒充真人独立签审。

## 首案（公开身份，仅元数据）

B 原始 SQLite 总体从 `6105` 条潜在任务，用 B 当前默认固定种子 `agentshield-bscale-auth-run-20261017-v1` 的 `select_task_ids` 排序首条：

- `request_id=rr-synth-00069697`
- `case_id=BSCALE-RR-SYNTH-00069697`
- `fixture_id=bscale-sim-rr-synth-00069697`
- `fixture_version=bscale-simulated-authorization-v1`
- `policy_version=a1-policy-v0.2-A-approved-D-pending`
- **模拟**客户消息含本次申请商品及数量的结构化累计确认，源 SQLite 的 `evidence_status=sufficient` 仅用于选择模拟情景，并非原始客户确认。
- A 候选允许结果：`completed`，无需转人工；合法金额及逐行 Gold 请见单独私有包，不放本文件。

## 单条生成（由 A/C 保管私有输出）

在 AgentShield 仓库根目录，且设定 Python 虚拟环境：

```powershell
python -m scripts.a_bscale_auto_gold `
  --source-db "D:\private\synthetic_merchant_v1.sqlite3" `
  --fixture-id "bscale-sim-rr-synth-00069697" `
  --out-private "D:\private\A_C_Gold\obligation_rr-synth-00069697.json" `
  --audit-private "D:\private\A_C_Gold\audit_rr-synth-00069697.json"
```

也可以通过 `--fixture <path>` 输入由 B 生成、**Agent 执行前**保存的公开 fixture JSON，不能输入运行证据。

**请使用 B 运行时 `fixture_content_sha256` 与 Gold 记录的 `fixture_canonical_sha256` 逐字节比较（均为规范化 JSON SHA256）；不等则停止核验。**

## 多条（C 提供已抽样 ID，A 不重复抽样）

```powershell
python -m scripts.a_bscale_auto_gold_batch `
  --source-db "D:\private\synthetic_merchant_v1.sqlite3" `
  --request-ids-file "D:\private\C_selected_request_ids.json" `
  --out-private-dir "D:\private\A_C_Gold\batch_01"
```

`request-ids-file` 支持 JSON 字符串数组，或者 B 已有 `batch_manifest.json` 的 `selected_request_ids`，1–10条。输出 private manifest、逐 case spec、SHA-256。

## C 接入（沿用已有接口，不修改 C 核心算法）

**务必先结束 Agent episode，再由隔离核验进程注入 Gold**：

```powershell
python -m experiments.reverify_evidence `
  --evidence "D:\private\actual_run\evidence.json" `
  --obligations "D:\private\A_C_Gold\obligation_rr-synth-00069697.json" `
  --out "D:\private\actual_run\post_obligation"
```

必须检查 C `LossResult.identity` 的四项：`case_id`、`fixture_id`、`fixture_version`、`policy_version`；它们与 Gold 逐字段一致。还要确认 `business_initial_hash` 与 EvidenceBundle 对应。已提交金额是交易事实；Gold 绝不基于实际退款推导。

## A → D 的两套保险计算（复用已有，不写第二套公式）

```powershell
python -m scripts.p0_insurance_display `
  --contracts "configs/insurance/research_products_P0_v0.1.json" `
  --loss-result "D:\private\actual_run\post_obligation\loss_result.json" `
  --output "D:\private\actual_run\post_obligation\claim_core_plus.json"
```

Gold 在 Agent 执行前不能判断非故意、授权 Agent/模型/工具、事故是否满足保单责任，故始终输出 `coverage_status_input=needs_review`。C 若核得 `loss_status=verified`，也不自动代表赔案已核定；A 需根据**实际执行证据**独立审核保单责任。责任未定时，Core/Plus 的 `payout_cents=null`，不等于0。已有 A0 `calculate_claim` 只在可保状态确定且损失已核实后计算，无需改动；必要的保险责任决议应独立留痕，不反改事前 Gold 或原始 C LossResult。

当前尚无此首案的真实 DeepSeek EvidenceBundle / LossResult；不得将免费 C 规则基线、旧 `bscale-r1` 样例或工程合成 LossResult 用作此次实际赔款。

## 测试与边界

- `python -m unittest tests.test_a_bscale_auto_gold -v`
- C 兼容性：在相同 revision 的 `evaluator.obligations.load_spec()` 和 `check_matches()` 验证，通过后检查不匹配版本必须拒绝。
- 已覆盖：有效模拟确认、部分退款整数尾差、历史退款占用、无结构化确认、数量冲突、客户不一致、商品资格、格式不匹配、版本拒绝、事后执行数据不可影响业务金额。
- 不支持的 B 新授权生成版本、复杂确认更正场景，必须停止并复核规则；本脚本不扩展新业务场景。
