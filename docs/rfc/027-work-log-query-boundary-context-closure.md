# RFC-027 — Work Log Query Boundary & Context Closure

Status: Proposed / Planning Baseline

> 本 RFC 仅定义 SP-018 规划基线。SP-018 实施尚未批准、尚未启动；本文中的模型、服务、API、CLI 和迁移路径均未实现。

## 1. 背景

AI-Lab 已能通过 CEO Assistant、`POST /work-logs` 和 Inbox resolution 写入工作记录，也能在 Daily Agenda 与 Daily Brief 中展示部分 Work Log。但是 Work Log 目前只是通用 Episodic Memory 中约定俗成的一类 JSON，没有唯一产品 Service、类型化记录、完整 Workspace 合同、稳定查询与 canonical ID。

SP-019 Daily Review 需要可靠的只读 Work Log 数据基础。SP-018 先收口 Work Log 自身，不提前实现 Daily Review、自动建议或主动推送。

## 2. Current State Audit

### 2.1 写入入口

| 入口 | 当前调用链 | 当前事实 |
|---|---|---|
| CEO Assistant | `_handle_work_log()` → `MemoryManager.save_memory()` | 保存 `type/raw_text/date/target/subject/status/tags`；随机 Memory ID；外层 metadata 仅含 session、agent、source |
| `POST /work-logs` | API → ApplicationRuntime → CEO Assistant | 只是给输入加 `记录:` 前缀；没有类型化 request/response 或 Workspace header 映射 |
| `python -m cli log` | CLI → ApplicationRuntime → CEO Assistant | 只有创建，没有 list/show |
| Inbox resolve | `InboxService.resolve_to_work_log()` → `MemoryManager.save_memory()` | 使用 `inbox_wl_...` 确定性 ID；`content.metadata` 含完整 Workspace，外层 metadata 仅含 workspace_id |

通用 Agent Runtime 也会写 Episodic Memory，但不是 Work Log 产品入口；SP-018 不改变其语义。

### 2.2 读取入口

| 消费者 | 当前读取方式 | 问题 |
|---|---|---|
| Daily Agenda | `MemoryManager.retrieve_memory(top_k=200)` 后 Python 筛 `type=work_log` | Workspace 只看 `content.metadata.workspace_id`；忽略 tenant/namespace；先截断后筛选 |
| Daily Brief | importance 排名前 10 的 Episodic Memory 后 Python 筛选 | 没有 Workspace、日期范围、稳定排序或分页 |
| CEO Assistant Chat context | 取最近 importance 前 5 条 Episodic Memory | 未严格限定 Work Log，也没有 Workspace |
| Tests | 多数直接查询 MemoryManager 后筛 `type` | 固化了 episodic.db 可读、重启持久化和旧 JSON 兼容事实 |

当前没有 Work Log list/get API，也没有 Work Log list/show CLI。

### 2.3 持久化与查询错位

`SQLiteEpisodicStore` 将 `content` 与 `metadata` 保存为两个独立 JSON 列，但 `MemoryQuery.filters` 对 `agent_id/session_id/source` 使用 `json_extract(content, ...)`。CEO Assistant 却把这些值写在 metadata 列。Store 查询固定 `ORDER BY importance DESC LIMIT top_k`，没有实现声明中的 offset、sort_by、Work Log 类型、完整 Workspace 或 ID 查询。

### 2.4 ID、时间和 Workspace

- 通用 `MemoryItem.id` 默认是无类型 UUID hex。
- CEO Assistant 的 `date` 来自 `datetime.now()`，没有注入 Clock，也没有持久化 IANA timezone。
- Inbox Work Log 使用注入 Clock 和系统 timezone，但 ID 为历史 `inbox_wl_...`，不是 `wl_...`。
- CEO Assistant 写入不保存 tenant/workspace/namespace。
- Inbox 的完整 Workspace 位于 `content.metadata`，与通用外层 metadata 不一致。
- 现有“Workspace 隔离”测试主要通过不同数据库路径隔离，不能证明同一数据库内的 WorkspaceKey 隔离。

### 2.5 隐含兼容合同

- 历史 Work Log 必须继续位于 `episodic.db / episodic_memories` 并在重启后可读。
- 旧记录可能只有 `date`、随机 ID 和不完整字段。
- Inbox resolution 依赖确定性 target ID 与既有 resolution claim；不得破坏其幂等与恢复。
- API/CLI/CEO Assistant 必须继续共享 canonical Composition Root。
- 读取不得写回、迁移或产生 LLM 副作用。

## 3. 目标

1. 建立唯一 `WorkLogService` 与类型化 `WorkLogRecord`。
2. 继续使用 `episodic.db / episodic_memories`，不创建新数据库或新表。
3. 新记录使用稳定 `wl_...` canonical ID 和完整 WorkspaceKey。
4. 提供 create/get/list、日期范围、过滤、稳定排序与分页。
5. 通过确定性只读投影兼容 legacy Work Log。
6. 只接受显式 canonical context reference。
7. 让 CEO Assistant、API、CLI、Inbox、Agenda 与 Brief 最终共享同一 Service。
8. 为 SP-019 提供只读基础，但不实现 SP-019。

## 4. 非目标

- update/delete 或复杂 Work Log 生命周期；
- 新建 `work_logs.db`、新表、跨库事务或跨库外键；
- 通用 Memory Layer 大重写；
- 自动写回、删除、复制或修复 legacy 记录；
- LLM 决定写 Intent、字段、关联或成功；
- SP-019 完整复盘、建议、催办、自动执行或主动推送；
- Recurring、通知、Web UI、Knowledge、插件框架、版本发布。

## 5. 产品使用场景

- 明确记录一条工作事实并获得 `wl_...` ID。
- 查询今天、日期范围、对象、标签、状态或文本相关的工作记录。
- 通过 canonical ID 查看单条记录。
- 显式关联 UserTask、Reminder、Waiting-For 或 Inbox。
- Agenda/Brief 在正确 Workspace 内读取相同的新旧记录。
- 任何模糊查询保持 READ、零副作用。

## 6. WorkLogRecord

规划模型：

```text
WorkLogRecord
- id: canonical wl_...
- workspace_key: tenant_id + workspace_id + namespace
- occurred_at: UTC aware datetime
- timezone: IANA timezone name
- subject: 1..500
- raw_text: 1..4000
- target: optional, max 200
- status: completed | in_progress | blocked | informational
- tags: normalized unique list, max 20, each 1..64
- source: ceo_assistant | api | cli | inbox | legacy
- context_refs: list[WorkLogContextRef], max 20
- created_at: persisted UTC timestamp
- legacy_memory_id: optional
- legacy_raw_status: optional
- schema_version: integer
```

新建默认 `status=completed`。tag 去首尾空白、空值丢弃、保持首次出现顺序并按 Unicode casefold 去重；不做同义词或 LLM 归一化。SP-018 只提供 create/get/list，不提供 update/delete。

## 7. WorkspaceKey

canonical scope 是：

```text
tenant_id + workspace_id + namespace
```

空值统一归一化为：

```text
default / default / default
```

每个 WorkLogService 方法都要求 WorkspaceKey。Repository 必须把完整三元组条件下推到 SQL；Handler、Agenda 或 Brief 不得先读取跨 Workspace 数据后再做主要隔离。

## 8. ID 合同

新直接创建记录：

```text
wl_<32 lowercase hex>
```

Inbox 确认创建：

```text
wl_<32 lowercase hex derived deterministically from inbox item id>
```

Legacy 展示：

```text
wl_legacy_<64 lowercase sha256 hex of legacy memory id>
```

新记录的 `episodic_memories.id` 与 `WorkLogRecord.id` 相同。随机 ID 冲突时重新生成并以 insert-only 重试；Inbox 确定性 ID 冲突只在来源一致时恢复，否则返回 conflict，禁止覆盖。Legacy digest 使用完整 SHA-256，避免截断碰撞；底层 legacy ID 只保留在投影字段，不作为公开 API ID。

## 9. 时间合同

- 新记录使用注入 Clock；未提供时间时取 `clock.now()`。
- `occurred_at` 持久化为 UTC aware ISO-8601，同时保存原 IANA timezone。
- 用户日期范围在请求 timezone 中建立边界，再转为 UTC 半开区间 `[start, end)`。
- today 使用系统 `timezone_name`，除非显式入口合同允许合法 IANA timezone。
- DST 由 `zoneinfo` 处理；不存在/歧义本地时间 fail closed。
- Legacy 投影优先级：可解析 `content.occurred_at` → 可解析 `content.date` → `MemoryItem.timestamp`。
- 只有日期的 legacy 值按系统 timezone 当地零点解释；绝不使用“当前时间”补造历史。
- 投影记录其时间来源，无法获得有效时间时返回 `work_log.legacy_projection_failed`，而非静默猜测。

## 10. 查询合同

```text
WorkLogService.create(workspace_key, command)
WorkLogService.get(workspace_key, work_log_id)
WorkLogService.list(workspace_key, query)
```

`list` 支持 `date_from/date_to/target/tags/status/text/context_ref/limit/offset/sort`。过滤条件之间为 AND；多个 tags 默认 all-of。文本查询只对 subject/raw_text/target 做 trimmed Unicode casefold substring，不做模糊相似度或 LLM 检索。空字符串无效。

默认 `limit=50`，范围 1～200；offset 范围 0～10000。默认且唯一首期排序：

```text
occurred_at DESC, id DESC
```

Repository 在完整 Workspace 与 `type=work_log` 条件内完成新旧投影、过滤、排序和分页。返回 `count/limit/offset/has_more/total_count`；`total_count` 是相同过滤条件下的精确可见数。跨页不得重复或遗漏。

## 11. 存储方案比较

### A. 专用 Repository/Adapter 复用 episodic 表 — 选择

```text
WorkLogService
→ WorkLogRepository protocol
→ SQLiteWorkLogRepository
→ episodic.db / episodic_memories
```

优点是类型化查询、Workspace、ID、分页、legacy 投影集中。Adapter 使用同一个 DatabaseManager lease 和同一行编码合同；WorkLogService 是 `type=work_log` 的唯一产品写入口。

### B. 继续通过 MemoryManager — 不选择

需要把 Work Log 的 ID、Workspace、分页、legacy 与产品过滤扩散进通用 MemoryQuery，容易污染通用 Memory 抽象，也保留“先 top_k 再筛选”的错误边界。

### C. 新建 work_logs.db — Rejected

会产生第二真相源、迁移/双写/重复风险和跨库协调负担，当前没有必要。

## 12. 选定架构

选择 A。Repository Adapter 与 `SQLiteEpisodicStore` 共享 `episodic_memories` 表和 DatabaseManager 所有权，但职责互斥：

- MemoryManager 继续服务通用 Episodic Memory；
- WorkLogService 是 Work Log 产品读写唯一入口；
- WorkLogRepository 只处理 `content.type=work_log`；
- 新 Work Log 使用 insert-only，不使用当前 `INSERT OR REPLACE` 覆盖语义；
- 不建立第二张表、不双写、不发布“已创建”成功直到同一行提交完成；
- 可抽取共享 row codec，但不得重写整个 Memory Layer。

首期允许在现有 JSON 列上使用 `json_extract`；不修改 Schema。Workspace SQL predicate 必须先于任何 Python 投影。若性能证据显示需要索引，必须另立 Schema 变更任务，不能在 SP-018 偷带。

## 13. Legacy 兼容

Legacy adapter 纯读取：

1. 识别 `content.type == work_log` 且 ID 不属于新 canonical 格式的行；
2. 生成 `wl_legacy_<sha256(memory_id)>`；
3. 保留 `legacy_memory_id` 与原始数据库行；
4. 缺失字段使用明确、可追溯的投影规则，不写回；
5. 新旧入口看到同一个投影 ID；
6. 重启后 ID 不变。

公开 get 只接受 canonical `wl_...` / `wl_legacy_...`。底层随机 Memory ID 不作为 API/CLI alias，避免泄漏通用 Memory 身份；Repository 内部维护 digest lookup。读取不创建 canonical 副本、不重复导入、不改变 importance。

## 14. Legacy Workspace

Legacy 行只有在能证明完整 Workspace 三元组时归入该 scope。缺少任一字段的旧记录只能属于 canonical default：

```text
tenant_id=default
workspace_id=default
namespace=default
```

不得按当前请求、session、人名或模型推断归属。已有 Inbox Work Log 的 `content.metadata` 完整三元组优先；只有外层单独 workspace_id 但缺 tenant/namespace 时仍按缺失完整 scope 处理为 default。

## 15. Context refs

```text
WorkLogContextRef
- kind: user_task | reminder | waiting_for | inbox
- target_id: ut_... | rem_... | wf_... | inbox_...
- relation: optional, max 64
- resolution: resolved | unresolved | not_checked
```

创建的强合同仅验证 canonical 前缀、字符、长度、kind 与 ID 一致、数量和重复项。SP-018 不在写事务内强制跨服务 existence check，因此依赖关闭、目标不存在或 Workspace 不匹配不阻塞 Work Log 创建。

读取可在对应服务可用时 best-effort 装饰 resolution；目标不存在、服务关闭或 Workspace 不匹配均返回 unresolved/not_checked，不删除引用，也不泄漏其他 Workspace 的目标详情。存储引用本身不声明外键或跨库事务。

## 16. API 规划

```text
POST /work-logs
GET /work-logs
GET /work-logs/{work_log_id}
```

POST 使用类型化 create request；GET list 使用 query parameters 和分页 response；GET item 返回同一 WorkLogResponse。三个入口从 `X-Tenant-ID`、`X-Workspace-ID`、`X-Namespace` 构建完整 WorkspaceKey。错误继续使用统一 FailureInfo/HTTP 映射。

旧的 ChatRequest 代理式 `POST /work-logs` 在实施时应兼容迁移到类型化 contract；不得同时保留两个写真相。

## 17. CLI 规划

```text
python -m cli work-log create
python -m cli work-log list
python -m cli work-log show <WL_ID>
```

CLI 通过 Composition Root 调用 WorkLogService，支持 JSON 输出、统一过滤、分页与 FailureInfo exit code。现有 `python -m cli log` 可作为兼容 alias，但必须委托同一 Service。

## 18. CEO Assistant 规划

规划最小拆分：

```text
WorkLogIntent
WorkLogInteractionHandler
WorkLogUserErrorPresenter
```

明确写入才 create；查询全部是 `IntentEffect.READ`、零副作用。支持 today、ID、target、tag、status、日期范围的确定性解析。模糊查询返回列表、示例或要求补充过滤条件，绝不降级成写入。LLM 可生成普通聊天文本，但不能决定持久化查询、字段、context ref 或成功。

## 19. Daily Agenda

实施后 Work Log 来源改为 WorkLogService：

- TODAY/COMPLETED：查询当天 `[start,end)`；
- ALL：使用明确上限和稳定分页，不再硬编码前后 365 天扫描；
- NEXT/ATTENTION：保持现有无 Work Log 来源语义，除非独立产品决策；
- 传完整 WorkspaceKey；
- legacy/new 使用相同投影；
- `source_id` 使用 canonical `wl_...`；
- Agenda 保持只读聚合，不把 Agenda 逻辑放入 WorkLogService。

## 20. Daily Brief

SP-018 只把 Brief 的 Work Log 来源从 MemoryManager 改为 WorkLogService，提供今日/最近记录、完整 Workspace、稳定时间范围与排序。Task/Reminder/Waiting-For 完整复盘、自动建议、自动写入和主动推送仍属于 SP-019 或后续。

## 21. FailureInfo

所有错误 `component=work_log`；Presenter 只替换 message。

| Code | Category | HTTP | CLI | Retryable | 中文提示 |
|---|---|---:|---:|---|---|
| `work_log.not_configured` | NOT_CONFIGURED | 503 | 2 | false | 工作记录服务未配置 |
| `work_log.not_found` | NOT_FOUND | 404 | 2 | false | 未找到该工作记录 |
| `work_log.workspace_mismatch` | PERMISSION_DENIED | 403 | 2 | false | 当前工作区无权访问该记录 |
| `work_log.id_invalid` | VALIDATION | 400 | 2 | false | 工作记录 ID 格式无效 |
| `work_log.subject_required` | VALIDATION | 400 | 2 | false | 请输入工作事项 |
| `work_log.occurred_at_invalid` | VALIDATION | 400 | 2 | false | 工作时间无效 |
| `work_log.timezone_invalid` | VALIDATION | 400 | 2 | false | 时区名称无效 |
| `work_log.query_invalid` | VALIDATION | 400 | 2 | false | 查询条件无效 |
| `work_log.limit_invalid` | VALIDATION | 400 | 2 | false | limit 必须在 1 到 200 之间 |
| `work_log.context_ref_invalid` | VALIDATION | 400 | 2 | false | 上下文引用必须使用受支持的 canonical ID |
| `work_log.repository_failed` | PERSISTENCE_FAILURE | 500 | 2 | true | 工作记录存储暂时不可用 |
| `work_log.legacy_projection_failed` | PERSISTENCE_FAILURE | 500 | 2 | false | 旧工作记录无法安全读取 |

details 只包含安全的 field、filter、ID 类型和 trace 信息，不包含 raw_text、凭据或其他 Workspace 数据。

## 22. 零副作用、安全与隐私

所有查询必须是 READ：零写入、零 event append、零 migration write-back、零 LLM side effect。Legacy 读取不补 Workspace、tags、refs 或 importance。Workspace mismatch 可用统一 403；不得用响应差异泄漏目标内容。日志与 FailureInfo 遵守现有敏感字段清理。

## 23. 性能与分页

Repository 先以 SQL 限定 `type=work_log` 和完整 Workspace，再做必要的 legacy 投影。为保证 legacy/new 混合分页正确，投影、过滤和排序属于 Repository，而非 Handler。初期在 local-first Alpha 数据规模内设 candidate cap 和可观测告警；不得因性能方便在 Workspace 过滤前截断。任何新索引或 Schema 变更需独立批准。

## 24. 测试与 ACC-018

ACC-018 A～O 规划覆盖 canonical create、Workspace、时间、ID、过滤、分页、legacy、context refs、Agenda、Brief、三入口一致、零副作用、重启真实进程与 FailureInfo。当前状态仅为 NOT_EXECUTED，不得引用规划测试作为通过证据。

## 25. 实施分阶段建议

1. Domain models、FailureInfo、Repository protocol/adapter 与 legacy projection。
2. WorkLogService create/get/list 和 Composition Root 注入。
3. CEO Assistant、API、CLI 与 Inbox 统一写入。
4. Agenda/Brief 只读消费者迁移。
5. ACC-018 自动化、真实进程与人工验收。

每阶段都必须避免双写；切换一个入口时，该入口只能指向 WorkLogService。

## 26. 风险

- 同表双入口可能覆盖或产生不一致写入；
- legacy JSON 形态多样，投影可能失败；
- 无索引 JSON 查询在大数据量下变慢；
- timezone/date 解释错误会改变历史排序；
- context ref 装饰可能泄漏跨 Workspace 存在性；
- Inbox 历史 `inbox_wl_...` ID 需要兼容投影而不能强改。

风险通过 insert-only、单一 Service、fail-closed Workspace、纯读 legacy、稳定 ID、边界测试与分阶段切换控制。

## 27. 回滚

实施回滚只撤回入口到 WorkLogService 的代码连接，不删除或重写 `episodic_memories` 行。由于不建新库、不做自动迁移，旧记录仍保持可读；已写入的 canonical `wl_...` 行仍是合法 Episodic Work Log，可由兼容读取识别。

## 28. Future Work

- SP-019 Daily Review & Follow-up Brief；
- 基于真实性能数据的 JSON expression index 或专用 Schema 决策；
- Work Log update/delete 生命周期；
- 经明确授权的 context target existence diagnostics；
- 更高级全文索引，但不由 LLM 决定写入。

## 29. 实施启动门禁

SP-018 实施前必须同时满足：

1. 本规划 PR 独立审查通过并合并；
2. 最新 main Quality Gate 成功；
3. Owner 明确批准实施；
4. 新实施分支从当时最新 main 创建；
5. 确认没有其他 SP-018/SP-019 实现分支或冲突；
6. RFC 由 Proposed / Planning Baseline 进入 Adopted；
7. 实施仍保持 `episodic.db`、无新表/新库、无 legacy 写回和无生产版本变更。

规划 PR 合并本身不批准实施。
