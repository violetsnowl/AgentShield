# B-CP2 候选案例目录

完整逐案例记录见 `CASE_MANIFEST.json`。金额单位均为整数分。以下分类是研究候选划分，不代表现实分布、正式 Gold 或已冻结留出。

## 数量

| 层级 | 常规候选 | 工程/压力候选 | 合计 |
|---|---:|---:|---:|
| L0 | 8 | 4 | 12 |
| L1 | 24 | 4 | 28 |
| 合计 | 32 | 8 | 40 |

L0 常规候选在 whole-low、whole-high、partial-low、partial-high 各 2 个。L1 常规候选在四类各 6 个，每类 3 个 estimate_candidate 和 3 个 holdout_candidate。

## 业务结构

常规 variant：

1. `clear_single`：单商品、唯一结构化确认。
2. `multi_item_discount`：多商品、多数量、优惠分摊。
3. `similar_orders`：相似订单，确认仅绑定目标订单。
4. `opening_history`：schema v2，会话前历史部分退款。
5. `corrected_confirmation`：前后确认更正，语义待审核。
6. `insufficient_information`：缺少结构化授权，应转人工。

工程/压力 variant：

- `injection`：客户自由文本试图覆盖系统规则。
- `conflict`：两条结构化确认冲突。
- `maximum`：30 个候选订单的受控结构边界。
- `ineligible`：有确认但资格为 false，应拒绝资金写入。

## 家族与划分

L1 常规 1/2、4/5 分别形成同划分内父子变体；3 和 6 是独立家族。estimate 与 holdout 家族集合不相交。L0 用于开发，不作为正式 L1 独立样本。case_id 稳定，session_id、episode_id、对象映射、交易和事件按每次运行隔离。

## 审核状态

所有 40 个候选均标记：

- `fixture_source=development_only`
- `review_status=pending_A_C_D_review`
- `candidate_resolution=unreviewed_candidate`
- `formal_sample=false`
- `known_net_loss_cents=null`
- `insurance_payout_cents=null`

A1 公共候选补丁未出现在本分支。本目录不能替代 A 的 28 个正式候选或 12 个工程候选的独立 Gold 审核。
