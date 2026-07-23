# SP-018 Work Log Query Boundary & Context Closure 验收规划

状态：IMPLEMENTATION_DRAFT / NOT_EXECUTED

规划日期：2026-07-23（Asia/Shanghai）

目标开发线：v0.35.0

当前源码版本：`0.34.0`

RFC：RFC-027 — Adopted

ADR：ADR-058、ADR-059、ADR-060 — Accepted

> 本文定义 ACC-018 A～O 的未来人工验收矩阵。Draft Head 的自动化验证不等于人工验收；没有场景已执行或通过。

## 固定边界

- 唯一逻辑真相边界计划为 `WorkLogService`。
- 物理存储继续使用 `episodic.db / episodic_memories`；不创建 `work_logs.db` 或新表。
- 新记录计划使用 canonical `wl_...` ID 和完整 WorkspaceKey。
- Legacy 仅做确定性只读投影，不写回、不导入、不删除。
- Context refs 只接受显式 `ut_/rem_/wf_/inbox_` ID。
- Agenda 与 Brief 计划通过 WorkLogService 读取。
- 查询必须 READ、零写入、零 event append、零迁移、零 LLM 副作用。
- SP-019 不在本验收范围内。

## 启动前提

执行 ACC-018 前必须具备：

1. SP-018 Planning Baseline 已审查合并；
2. Owner 明确批准实施；
3. RFC-027 已进入 Adopted；
4. 实现 PR 的 Approved Head 已固定；
5. 最新 main Quality Gate 成功；
6. 隔离数据目录、真实 API/CLI 进程与无 Provider 凭据环境已准备；
7. 产品版本、Tag、Release 仍按独立版本治理处理。

## 自动化与人工证据要求

每个场景必须同时记录：

- 实际命令或 HTTP request；
- WorkspaceKey；
- 创建/读取到的 canonical ID；
- 数据库行数与必要字段快照；
- 前后副作用对比；
- 进程、重启或并发条件；
- FailureInfo 全字段；
- 对应自动化测试名称和真实结果。

任何无效 harness、编码错误或 driver 断言错误必须单列为 `INVALID_ACCEPTANCE_HARNESS`，不得计作产品失败或通过。

## ACC-018-A：Canonical create

通过 WorkLogService 创建新记录，验证：

- 返回 `wl_<32 lowercase hex>`；
- row ID 与 WorkLog ID 相同；
- 持久化到既有 `episodic.db / episodic_memories`；
- 完整字段、WorkspaceKey、UTC occurred_at、IANA timezone、source、schema_version；
- 重启后 get 返回相同对象；
- 没有 `work_logs.db`、新表或双写。

状态：NOT_EXECUTED

## ACC-018-B：Workspace 隔离

在不同 tenant_id、workspace_id、namespace 组合创建记录。逐项验证 create/get/list、ID lookup、filter 和分页均只返回完整三元组匹配的数据；仅 workspace_id 相同不能越权。

状态：NOT_EXECUTED

## ACC-018-C：Today 与日期范围

验证系统 timezone、显式合法 IANA timezone、UTC 转换、`[start,end)`、午夜边界、DST 边界、date_from/date_to 和无效/歧义时间 fail closed。不得用当前时间补造 legacy 时间。

状态：NOT_EXECUTED

## ACC-018-D：Canonical ID 查询

覆盖：

- 新 `wl_...`；
- `wl_legacy_...`；
- 不存在 ID；
- 非法 ID；
- Workspace mismatch；
- 已完成历史 Inbox-to-Work-Log 仍从 Inbox 返回 `inbox_wl_...`；
- WorkLogService 接受合法历史 `inbox_wl_...` alias，并返回 canonical `wl_legacy_<full sha256>`；
- alias 与 canonical ID 再次 get 返回同一对象，不创建新行；
- 重启后 alias 映射不变；
- Inbox alias Workspace mismatch fail closed；
- 普通随机 Memory ID 仍不作为公开 alias。

状态：NOT_EXECUTED

## ACC-018-E：过滤组合

覆盖 target、tags、status、text、context_ref 和 date range。验证条件间 AND、多 tags all-of、Unicode casefold substring、空字符串拒绝，以及过滤不会跨 Workspace。

状态：NOT_EXECUTED

## ACC-018-F：稳定排序和分页

创建相同或接近 occurred_at 的新旧记录，验证：

- `occurred_at DESC, id DESC`；
- limit 1～200；
- offset；
- count、has_more、total_count；
- 跨页无重复、无遗漏；
- invalid limit/offset 明确失败；
- 不按 importance 排序；
- 数据量超过 slow-query/scanned-row observability warning threshold 时仍返回精确 total_count；
- 告警不截断分页、不改变 count、has_more、排序或结果；
- Workspace filter 在分页和计数前生效；
- 不存在业务结果 candidate cap。

状态：NOT_EXECUTED

## ACC-018-G：Legacy 可读兼容

注入多种旧随机 Memory ID Work Log，验证：

- 可由 Service 读取；
- `wl_legacy_<full sha256>` 稳定；
- 重启、API、CLI、Agenda、Brief 身份一致；
- 保留 legacy_memory_id；
- 不创建新行、不重复导入、不改变原行或 importance；
- legacy projection failure 可见且查询 fail closed；
- 历史 Inbox row 投影为稳定 `wl_legacy_...`，Inbox 仍保留 `inbox_wl_...`；
- alias 与 canonical 查询零写入、重启后身份不变；
- 普通随机 Memory ID 仍被拒绝。

状态：NOT_EXECUTED

## ACC-018-H：Legacy Workspace fail closed

验证缺少完整 Workspace 的旧记录只在 `default/default/default` 可见；只有 workspace_id 或 session metadata 不足以归属其他 scope。读取不得自动补齐或重新归属。

状态：NOT_EXECUTED

## ACC-018-I：Context refs

显式保存和查询 `ut_`、`rem_`、`wf_`、`inbox_` 引用。验证 kind/prefix、重复、长度、非法前缀 fail closed；服务关闭时 `not_checked`，不存在或 Workspace 不匹配时 `unresolved`，且创建不被非事务性 existence check 阻塞。不得自动猜测。

状态：NOT_EXECUTED

## ACC-018-J：Agenda 统一消费

Daily Agenda 必须：

- 通过 WorkLogService；
- 传完整 WorkspaceKey；
- TODAY/COMPLETED 使用当天半开区间；
- ALL 使用稳定查询；
- legacy/new 都可显示；
- source_id 使用 canonical `wl_...`；
- 不直接扫描 MemoryManager；
- 查询前后零写入。

状态：NOT_EXECUTED

## ACC-018-K：Brief 统一消费

Daily Brief 的 Work Log 数据必须来自 WorkLogService，具有正确 Workspace、稳定时间范围、排序与 ID。验证没有扩展 Task/Reminder/Waiting-For 完整复盘、自动建议、自动催办、自动写入或主动推送。

状态：NOT_EXECUTED

## ACC-018-L：API / CLI / CEO Assistant 一致

从三个真实入口创建和查询，验证：

- 同一 Service 与 episodic.db；
- 同一 canonical ID、Workspace、字段、排序、分页；
- 相同 FailureInfo code；
- API Workspace headers 生效；
- `python -m cli log` 兼容 alias 不形成第二写路径；
- 明确 query intent 为 READ；
- 已完成 Inbox resolution、API、CLI、CEO Assistant、Agenda 与 Brief 对同一 Work Log 返回一致 canonical `wl_legacy_...`；
- Inbox 自身历史字段继续返回 `inbox_wl_...`，重复 resolve 不创建 `wl_...` 新行。

状态：NOT_EXECUTED

## ACC-018-M：查询零副作用

在每类 query 前后比较：

- episodic row count；
- 所有 Work Log content/metadata/importance/timestamp；
- EventBus 事件；
- legacy row；
- context refs；
- LLM 调用计数。

必须证明零写、零 event append、零 write-back、零自动迁移、零 LLM side effect。

状态：NOT_EXECUTED

## ACC-018-N：重启和真实进程

使用独立 CLI 进程与真实 Uvicorn API 进程，共享一个隔离 SQLite data dir，覆盖 create/list/get、Workspace、legacy/new、重启与并发读取。所有进程必须看到一致 ID、排序和字段。

状态：NOT_EXECUTED

## ACC-018-O：FailureInfo 与 Presenter

至少覆盖：

- `work_log.not_configured`
- `work_log.not_found`
- `work_log.workspace_mismatch`
- `work_log.id_invalid`
- `work_log.subject_required`
- `work_log.occurred_at_invalid`
- `work_log.timezone_invalid`
- `work_log.query_invalid`
- `work_log.limit_invalid`
- `work_log.context_ref_invalid`
- `work_log.repository_failed`
- `work_log.legacy_projection_failed`

注入 `content` 非 dict、type 非 work_log、缺 subject/raw_text、安全时间缺失、非法 row id 与非法持久化 timestamp。验证非 Work Log 不进入 list、exact Inbox alias 对非 Work Log 返回 not_found，而符合 Work Log type 但无法安全投影时整个查询以 `work_log.legacy_projection_failed` fail closed，details 只含安全 row identity digest。

验证 category、HTTP、CLI exit code、retryable、details、trace_id 一致；中文 Presenter 只能改变 message，不得改变机器字段。

状态：NOT_EXECUTED

## 通过条件

只有 A～O 全部在 Approved Head 上真实执行通过，独立审查为 APPROVED，PR 与 post-merge main Quality Gate 均成功，并完成治理对账，ACC-018 才可更新为 `PASSED / FINAL`。任何部分覆盖、计划测试或旧 Memory 测试都不能替代该结论。
