# FRONTEND_OBSERVATIONS

## 实际启动方式与边界

- 生产前端由本地工作台真实启动于 `127.0.0.1:8810`。
- 使用独立库 `var/integration-20261015/visible-qa.sqlite3`；没有读取或覆盖原工作台库。
- 通过 Codex in-app browser 实际点击四区、切换 B session 与 A/C 运行、加载关联证据、刷新、前进/后退。
- 联调结束后服务已停止；浏览器控制台错误/警告为 0。

## 四区实测

- Ⅰ 企业实验场：可列出受控模板和隔离 session；业务消息、订单、商品、333 分开发退款事实一致。
- Ⅱ 执行证据/账本：事件、交易、退款、账本和人工工单可追到同一 session；资金守恒；观察者没有写入。
- Ⅲ 风险/配置比较：可选择最终规则基线批次，显示 `counts_as_formal_run=false`、`scripted_test`、0 元模型成本、LossResult 状态；“加载关联业务证据”能切到精确 B session。
- Ⅳ 合同/情景成本：A0 合同、免赔、比例、限额、`needs_review/null` 可见；工程 B0/B1 样例明确标为 illustrative，B2 为 `not_fitted`，浏览器不能重算。
- 刷新：保持合法 area/run 选择并重新读取。
- 浏览器回退/前进：URL、可见区和视觉 active 状态一致；未出现跨区资金调用。
- 上下文串台：B 当前 session 与所选 A/C 历史 run 不同时有明确提示，只有用户点击“加载关联业务证据”才切换。

## 已修复问题

- P1：规则基线的 `scripted_test` 被前端当作未知来源。修复 parser union 和运行标签，新增前端测试；页面现在显示“规则基线”。

## 保留给前端同学的问题（本轮未重构）

- P2：全局模板选择器一次显示约 44 项，运行选择器同时显示真实开发、Mock、首轮错误批次和修复批次，信息密度高，缺少批次折叠/状态筛选。
- P2：历史错误批次 `...-201056` 与最终批次并列展示，没有 `superseded` 标记；不能删除历史证据，但应提供显式状态。
- P3：页头运行身份、风险卡片、合同卡片多次重复 session/episode/config/source；可读但冗余。
- P3：合同页同时显示当前运行的 A0 结果和“非本次运行”的工程成本样例，标签正确但认知负担较大。
- 后端/产品缺口而非前端错误：目前只有一个研究合同，没有两套已批准保险产品和商业保费；前端正确保留待确认，没有写死价格。

## 截图与自动化证据

最终核心目录：`artifacts/pro_bd_sprint/05/integration-final-browser-core-20261015/`，18 张截图；重点包括：

- `core-lab-v1-desktop.png`
- `core-ledger-v1-desktop.png`
- `risk-candidate-desktop.png`
- `cost-candidate-desktop.png`
- `offline-schema1-desktop.png`、`offline-schema2-desktop.png`、`offline-schema3-desktop.png`
- `lab-v2-mobile.png`

最终 Stage04 目录：`artifacts/pro_bd_sprint/05/integration-final-stage04-20261015/`；重点包括：

- `integration-first-screen-1366.png`
- `integration-order-trace-1366.png`
- `integration-risk-candidate.png`
- `integration-cost-candidate.png`
- `integration-mobile.png`
- `contradictory-replay-rejected.png`

结果：核心 737 项 PASS / 18 图；Stage04 117 项 PASS / `errors=[]`。
