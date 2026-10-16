# AgentShield A-P0：B→C→A→D 最小联调交付（2026-10-16）

**状态**：A 的程序与研究参数候选已完成本地校验；真实 `A1-W_L-01` 的 DeepSeek 保存证据和第二真人正式签审尚未交付本次审查，因此**不得认定为真实保险赔付**。不调用付费模型，不更改 B 账本，不调整 C Agent。

## 1. 现有接口与最小增量

- `experiments/reverify_evidence.py`：**现有 C 程序可直接使用** `evaluator.obligations.load_spec` 读取 A4 私有 `gold-A1-W_L-01.json`。不需修改 spec 格式或重跑模型。
- `actuarial.claims.calculate_claim`：继续使用 A0 单事件赔款函数，保留 `needs_review → payout_cents=null` 规则。
- 本次新增：`configs/insurance/research_products_P0_v0.1.json`、`scripts/p0_insurance_display.py`、`scripts/p0_premium_evidence.py`、研究示例 JSON 和测试。不修改旧 A4 JSON 或交易、Agent、D 页面。

## 2. P0-1：私有 Gold 对接边界（公开说明，不包含私有答案）

`A1-W_L-01` 的公开 fixture 是 `a1-w_l-01-r2`，业务政策为 `a1-policy-v0.2-A-approved-D-pending`。A4 obligation spec 的完整 JSON、`spec_id`、合法应退商品/数量/金额、复核记录、Gold 文件哈希，均在**私有审核包**中，本公共包不重复公开答案。

A 已验证该私有 spec 符合 C 当前 `evaluator.obligations.load_spec` 和身份匹配规则。第二位真人复核签审记录尚未随本次材料提供，故 Gold 仍为候选，保障责任仍待审核。

C 使用方式：必须在 Agent 运行**结束后**，在独立核验环境执行下列命令；所有真实证据和 Gold 路径都应为私有路径，绝不从 Agent 的运行器或提示词目录获取 Gold：

```powershell
python -m experiments.reverify_evidence --evidence "<已保存真实证据文件>" --obligations "<隔离Gold目录>\gold-A1-W_L-01.json" --out "<隔离输出目录>\reverified_wl01"
```

运行前先核对 B/C EvidenceBundle 的 `case_id, fixture_id, fixture_version, policy_version` 与私有 spec 一致。若核验器给出 `loss_status=verified` 但保障责任仍为 `needs_review`，赔款字段仍须 `null`，不能显示0或标为已赔付。

## 3. P0-2：两个可展示的研究合同

| 参数 | Core | Plus |
|---|---:|---:|
| 单事件免赔额 | 100元 | 50元 |
| 赔付比例 | 80% | 100% |
| 单事件赔付限额 | 1000元 | 5000元 |
| 年累计赔付限额 | 100000元 | 500000元 |
| 年累计限额的实际算法 | **暂未实现** | **暂未实现** |
| 附加应急处置费用 | 不保 | 当前未计入；未来可选择设计 |

上述均为有意设置的**研究假设参数**，不是依据真实损失统计拟合的商业保额、免赔或费率。Core 保留 A0 基础例中的100元免赔和1000元限额，设80%参与展示共同承担；Plus 将免赔减半并以研究订单5000元上限作为对比上限，100%参与。年度上限用于产品展示和解释风险边界，**不能暗示已被A0逐事件理算程序执行**；未来真正的累计赔付需按年度事件发生顺序逐笔扣减。

公式（两合同一致） `I = min(u, ROUND_HALF_UP(max(L_H-d,0) * c), L_H)`。金额全为整数分，`c` 用万分比；事件免赔只扣一次，限额是单事件已赔金额上限，不是总损失上限。

## 4. P0-3：D 可直接加载的双合同 JSON

在现有项目根目录执行：

```powershell
python -m scripts.p0_insurance_display --output "artifacts/insurance_p0/display.json"
```

展示结果（仅**工程场景**、与真实模型事故无关）：

| 场景 | 净额外损失 | Core赔款 | Plus赔款 | 状态 |
|---|---:|---:|---:|---|
| 正常：应退80元，实退80元 | 0元 | 0元 | 0元 | `engineering_illustration` |
| 超退：应退80元，实退800元，追回200元 | 520元 | 336元 | 470元 | `engineering_illustration` |
| 真实W_L_01尚无核验与责任批准的示意占位 | null | null | null | `observed_run_not_formally_admitted`（**不是实际运行结果**） |

手算：`L_H=(800−80)−200=520元`。
Core：`min(1000,(520−100)×0.8,520)=336元`，企业自留184元。
Plus：`min(5000,(520−50)×1,520)=470元`，企业自留50元。
注意这笔520元是历史 A0 已设计的**人工工程算例**，不包含任何声称真实 DeepSeek 出错的证据。

D 可直接消费随补丁提交的 `docs/handoff/P0_display_examples/P0_claim_comparison_engineering.json`（运行时也可动态生成 `artifacts/insurance_p0/display.json`），每个 `examples[]` 有 `source_type`、`net_loss_cents`、`claims[]`。`claims[]` 含 `contract_version`、`claim_status`、`payout_cents`、`retained_loss_cents`、`annual_aggregate_calculation_status`。界面按 `source_type` 明确展示 “ENGINEERING / PENDING”，对 null 输出「待核验」，不得渲染成 ￥0，不得写“已赔付”。

**接入真实保存 LossResult（本包没有伪造真实文件）**：

```powershell
python -m scripts.p0_insurance_display --loss-result "<独立核验输出目录>\loss_result.json" --output "<输出目录>\real_case_claim_comparison.json"
```

此入口不擅自改变 C 的 `coverage_status_input`。如果仍 `needs_review`，则两合同赔款均保持 null；这代表保障责任未审核，不是赔款0。

## 5. P0-4：保费第三页应当显示什么

当前不能估计有依据的年度**情景纯风险成本**，理由：四个固定开发案例不是按业务结构代表性抽样的独立风险样本；真实 DeepSeek 记录未附完整核验证据和 A 责任批准；每类需要独立 case 样本均赔款，不能直接用退款金额当损失；重大异常的尾部分布未估计。即使 10万订单总样本推导出 V 和四类权重，也不足以自动补足 `E[payout|g]`。

需要的最小输入：研究范围/保障版本、年度 Agent **任务数** V（订单数不是任务数）、四类权重 w_g、正式案例及重复运行的**按独立 case 聚合**的四类可保赔款均值 µ_g、合同及证据来源、未核验比例、观察时点H、追回。年度限额/真实商业报价另需事故时间顺序、尾部、共同事故、费用/再保/资本/利润等。

**第三页可以展示**：两种保障条款与保额、工程索赔对比图、`insufficient_evidence`、需要补齐的输入清单、研究公式 `V × Σ w_g µ_g`。不得将工程赔款、零观测或未知状态换算成商业保费。

可运行保费证据闸门（当前输入空缺时返回 insufficient）：

```powershell
python -m scripts.p0_premium_evidence --input configs/insurance/P0_premium_input_template.json --output "artifacts/insurance_p0/premium.json"
```

如果未来团队先**明确声明研究假设**，将四类赔款均值、V 和 w_g 全部填入模板并置 `estimate_source=research_assumption`，则程序可以计算 `illustrative_assumptions_only` 的纯风险成本，不包含累计限额、费用或利润率，`commercial_premium_cents` 始终 null。若要使用审核后的正式估计集，还需保存来源和验证记录；程序给出的仍只是限定样本研究值。

## 6. 测试及真实边界

当前本机在合并历史 ABCD＋A1＋A3＋A4 的基础上新增 P0 代码：完整 Python `155/155 OK`；P0 新增 `8/8 OK`；C `load_spec`/`check_matches`、四元身份、商品行金额与前版两个 SHA-256 验证通过。**这不是你们2026-10-16最新 Windows 整合环境/DeepSeek 实际 EvidenceBundle 的测试；仍需 C/D 本机执行。**

禁止将 `A_D_PRIVATE_DO_NOT_COMMIT` 上传公开 GitHub 或打包进前端静态资源。不要改变 A4 Gold 的 pending 状态。提交 A 分支公共内容时不覆盖 A0/A4 核心文件。当前本包未执行 Git Push。
