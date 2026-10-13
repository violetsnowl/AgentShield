# BD 本机观察者接口候选 observer-0.1-candidate

2026-10-12，阶段 03。B/C 保持 bc-0.3-candidate、七工具、EvidenceBundle schema 3、迁移 001/002/003。此候选仅为 D 读取和受控开发会话创建提供接口；不新增 A/C 正式结果协议，不改变交易与幂等语义。

## B 的最小增量

- 管理鉴权 GET `/api/v1/admin/fixtures`：FixtureCatalog，只返回注册表中两个开发模板的 ID、版本、源 case、政策、来源与待审状态，不接受模板文件路径。
- 管理鉴权 GET `/api/v1/admin/sessions?tenant_id=...&offset=0&limit=25`：SessionPage。tenant_id 必填；offset ≥ 0，limit 1–100；按插入顺序倒序返回 SessionStatus 与 next_offset。无 token、无跨 session 聚合。
- 原管理 GET `/api/v1/admin/sessions/{sid}/events?after_seq=0` 增加可选 limit 1–100；省略 limit 保持原行为。EventPage 仍是 events、last_seq，无虚构 attempted/committed 状态枚举。新读取在 SQL 中限制条数，seq 仍为原始序列。

其他工具、EvidenceBundle、快照和迁移不变。已有 B/C 客户端不需改变工具调用；严格检查整个 OpenAPI/模型目录的消费者会看到新增的三个只读目录模型和两条管理路由，应审阅更新后的导出文件。

## 浏览器 → 本机观察者 → B

同源请求使用 `X-Workbench-Request: 1` 和独立观察者 HttpOnly cookie。POST 还要求精确本机 Origin；GET 允许浏览器同源时省略 Origin，但保留自定义头、Host 和 Sec-Fetch-Site 检查。没有 CORS 开放。B 的 Authorization 由服务端 httpx 添加，trust_env=false，不跟随重定向，上游地址仅允许明确的 127.0.0.1 HTTP origin。

- POST `/observer/pair`：本机启动器一次性 120 秒授权交换，最长一小时观察者 cookie。不是 B session_token；不打印、不持久化到 JS 存储，URL fragment 在首个请求前移除。授权状态仅驻留服务器内存，重启即失效。
- POST `/observer/logout`：撤销当前观察者 cookie。
- GET `/observer/api/fixtures`：映射到 B 模板目录。
- GET `/observer/api/sessions?offset=0&limit=25`：服务器强制观察租户，不接受浏览器指定 tenant。
- POST `/observer/api/sessions`：仅 `{fixture_id}`，Literal 只允许 v1/v2。服务器强制 tenant、scripted_test、workbench-development 和 unexecuted-development-session；剔除并丢弃 B 一次性运行令牌，只返回 session/context。
- GET `/observer/api/sessions/{sid}/evidence`：B EvidenceBundle；两个快照均必须属于指定 sid 与观察租户。
- GET `/observer/api/sessions/{sid}/events?after_seq=0&limit=10`：先验证范围，再读 B 原始事件页。
- GET `/observer/api/sessions/{sid}/ledger`：先验证范围，再读 B 账本。

没有 PUT/PATCH/DELETE、工具执行、工单裁决、报价、任意代理路径或上传接口。未知路由无转发。观察者读取不会添加工具事件，也不能用管理员权限代跑 Agent。只有本机可信开发操作者可以启动服务；这不是多用户认证或公网部署方案。

## 事实与显示边界

ToolEvent 真实状态仅 succeeded/rejected/replayed/error。读取 succeeded 不代表付款；人审工单是持久化事实但资金为零；finish 仅声明；replayed 返回原结果但新提交金额为零。页面退款汇总只求和已提交退款记录，拒绝重复 transaction_id，不从事件结果反复计钱。账本直接显示 B 的双边 delta/balance，通过 transaction_id/call_id/order_id/seq 关联，不复制退款算法或 A 公式。

Evidence/事件页/账本并发读取后校验同一次 session 与内容；若运行期间变化导致不一致，提示刷新，不混合旧新事实。切换运行清掉旧显示、取消旧请求；迟到的旧响应不覆盖新选择。case 只用于关联，不用作运行缓存键。旧 case 显示“按原记录”，缺少上下文不生成稳定映射或哈希。

schema 1/2/3 使用 B 原始 JSON Schema 的预编译浏览器校验器；导入还拒绝凭据字段、混合 session/episode、重复 seq/交易、不安全整数金额和未声明 schema。缺失历史 human_reviews 与显式空数组分开显示。原 v1 政策在原证据中未改写。

## 实际样例与联调

`contracts/workbench_examples.json` 来自 `artifacts/pro_bd_sprint/03/final_browser_evidence` 的真实 loopback 捕获，包括模板目录、会话页、两页事件、去凭据的观察者创建响应。完整两模板证据/事件/账本与 browser_results.json 同目录。开发脚本样例的 333/250 分是实际 B 提交的模拟资金事实，不是 C 成绩。

加载、502、8 秒超时和全局空列表的浏览器检查使用**测试脚本的受控网络注入**，文件名含 `-test-`；不进入生产代码，不当作真实业务故障样本。无事件/资金的新会话来自真实创建。offline-schema1/2 使用历史保留证据，offline-schema3 使用本次网页真实下载文件。断网时只读文件仍可显示，但未实现网页冷启动和 A 离线理算。

## 待审

A/C/D 审核案例/政策语义、v1 历史文字与当前能力差异；C 独立确认工具尝试/本地失败/响应接收边界及候选协议；BD 下一位开发者确认本机授权和观察租户适合后续接入。没有代签 A/C，没有声明 J0/J1/J2 或 L1 R09 通过。
