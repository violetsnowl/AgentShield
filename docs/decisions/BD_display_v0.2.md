# BD 展示边界候选 bd-display-0.2

阶段 04 增量记录，待 A/C/BD 审阅。B/C bc-0.3、observer-0.1 的 HTTP 字段和权限不变。没有对 LossResult/QuoteResult 另起正式协议。

展示端使用 B 生成的 schema 1/2/3，补充事实等式核对。退款必须有唯一对应账本，行金额之和等于退款；账本双边增量与退款一致；按照已记录 session_version_after 核对逐笔余额；期末等于期初加变化；订单/商品已退增量与退款事实一致。事件 succeeded/rejected/replayed/error 和资金提交分开，错误/重放/查询不新增提交。已记录身份归属不一致或交易关联破损时拒绝进入正常展示。

这不是 B 退款资格判定、C LossResult 或 A QuoteResult 的替代。历史缺失成功事件时明示追溯未验证，不补事件；缺失工单不同于空数组。业务初态 hash 明示文件声明值未复核，canonical 内容不自动升级为已验证初态。所有导入均本地只读，没有上传和执行入口。

异步交互序号覆盖创建、导入、返回本机、目录重试、读取及选择运行；旧异步完成只能被丢弃，不能改写较新选择，也不撤销服务端事实。B 创建响应丢失时仍需核对目录，不可认定取消浏览器等待就没建会话。

运行筛选只作用于已加载目录，event 筛选只作用于已加载事件；总计始终来自当前 bundle 的退款，不能用可见行求资金总和。case 可关联重复运行，但没有按 case 合并状态或账本。transaction 跳到精确 order，长 ID 可展开/复制。

A/C 边界为 bd-results-boundary-0.1-candidate：未知输入类型 + 未审版本拒绝 + 空值 pending。V1.1 四种状态作为说明，不冒充正式结果。商业报价始终不可用，commercial_quote=false。最小语义需求、实例/导出路径、样例与待审问题见 docs/handoff/BD_to_A_C.md。
