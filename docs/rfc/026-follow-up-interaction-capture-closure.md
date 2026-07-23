# RFC-026 — Follow-up Interaction and Capture Closure

Status: Adopted

## 背景与当前能力审计

SP-016 已交付独立 canonical Waiting-For domain、`followups.db`、append-only event、workspace 隔离、乐观并发、API/CLI 生命周期入口及 Daily Agenda 可选来源组合。ACC-016 已通过并封存，因此 SP-017 不重做 Waiting-For 模型或生命周期。

当前代码边界如下：

- `applications/ceo_assistant/intent.py` 已区分 READ / WRITE / CHAT，Reminder 查询优先于模糊写入，支持 Inbox capture/list、明确写命令，并在歧义时优先读取；尚无任何 `waiting_for_*` intent。
- `applications/ceo_assistant/application.py` 已注入 `InboxService` 与 `DailyAgendaService`，没有注入 `WaitingForService`，也没有 Waiting-For handler。Agenda 文本映射尚未把内部来源值 `waiting_for` 展示为“等待事项”。Chat/LLM 只能生成对话文本，不能成为 Waiting-For 写入执行器。
- Inbox 当前可显式转为 UserTask、Reminder、Work Log、Note 或 Dismiss，尚不支持 Waiting-For。`inbox_resolution_claims` 已提供 `CLAIMED`、`TARGET_CREATED`、`COMPLETED` 三阶段持久化恢复边界。
- `WaitingForService` 已提供 create、get、list、history、follow-up、snooze、resolve、cancel、reopen；SP-017 不改变这些 canonical lifecycle 语义。
- `/waiting-for` API 与 `waiting-for` CLI 已提供显式创建和完整生命周期。Inbox API/CLI 尚无 `resolve/waiting-for` 或 `resolve-waiting-for`。
- canonical Composition Root 已创建 `WaitingForService` 并注入 Daily Agenda，但尚未把它注入 CEO Assistant 或 InboxService。

## 产品目标与安全原则

SP-017 建立“确定性 Follow-up 交互 + Inbox 持久化确认 + Waiting-For 生命周期操作”的产品闭环：

```text
模糊或待确认的自然语言
  → 捕获为 Inbox Item
  → suggested_type=waiting_for
  → 用户通过 Inbox ID 明确确认
  → 复用持久化 resolution claim
  → 创建唯一 Waiting-For
  → 通过 Waiting-For ID 执行后续生命周期
```

用户应能查看正在等待什么、查看需要催办的事项、暂存候选、确认创建、记录催办、延期复查、解决、取消、重新打开并查看完整历史。

安全原则：读取可以自然；写入必须明确；自然语言创建必须经过持久化确认；歧义不得产生业务对象；LLM 输出不得作为写入依据或成功证据。

## 三层交互模型

### 第一层：Read

读取不产生副作用，可直接执行。

示例：

```text
查看等待事项
我在等谁回复
有哪些需要催办的事项
查看等待事项 wf_x
查看 wf_x 的催办历史
```

对应 intent 与 effect：

| Intent | Effect |
|---|---|
| `waiting_for_list` | READ |
| `waiting_for_detail` | READ |
| `waiting_for_history` | READ |

### 第二层：Capture

当用户表达可能的等待事项但尚未完成结构化确认时，例如“等张经理回复蜂蜡检测方案”“张经理还没回复检测方案”或“先记下来，等客户确认报价”，系统只创建 Inbox Item：

```text
suggested_type = waiting_for
status = pending
```

对应 `waiting_for_capture` / WRITE。该写入只允许创建 Inbox Item，不得创建 Waiting-For、Reminder 或 Scheduler Job。

### 第三层：Confirm / Lifecycle

自然语言创建必须通过明确 Inbox ID 确认，例如：

```text
把 inbox_x 整理成等待事项：
等待张经理回复蜂蜡检测方案，
明天下午三点再看
```

确认后才允许创建 Waiting-For。后续写入必须使用 canonical Waiting-For ID：

```text
催办 wf_x：已通过微信联系
把 wf_x 延后到明天下午三点：对方出差
解决 wf_x：已经收到回复
取消 wf_x：客户不再需要
重新打开 wf_x：还需要补充材料
```

不得仅凭模糊标题或人名修改状态。

## 创建确认边界

CEO Assistant 自然语言入口不得一步直接调用 `WaitingForService.create()`。唯一自然语言创建路径是：

```text
Inbox capture
→ explicit confirmation
→ InboxService.resolve_to_waiting_for()
```

这样可以避免人名、事项和时间提取不完整，允许用户看到结构化结果后确认，并复用持久化 claim 提供幂等与崩溃恢复。文本相似度或 LLM 不参与去重。

现有显式入口 `POST /waiting-for` 与 `python -m cli waiting-for create` 继续允许单步创建；它们不受自然语言两阶段边界影响。

## 创建所需字段

Inbox 转换为 Waiting-For 时必须具备：

- `subject`
- `waiting_on`
- `next_review_at` 或 `expected_by` 至少一个

缺少字段时，Inbox Item 保持 pending，不创建 Waiting-For，返回明确缺失字段并给出可复制的确认命令模板。不得使用 LLM 猜测缺失值。

## 确定性时间范围

SP-017 只复用现有经过验收的确定性时间子集：今天、明天、上午、下午、晚上、明确小时、现有分钟形式、有效 IANA timezone 与明确 ISO-8601 offset。

不新增下周、月底、过几天、尽快、有空时、每周、每月、模糊相对时间或 LLM 时间解析。无法确定的时间不得写入。

## Inbox 类型扩展

规划增加：

```python
InboxSuggestedType.WAITING_FOR = "waiting_for"
InboxResolvedType.WAITING_FOR = "waiting_for"
```

`WAITING_FOR` 属于 external target 类型：claim 的 `target_key` 必填；`TARGET_CREATED` / `COMPLETED` 时 `target_id` 必填；不修改现有 claim 状态机。

目标 ID 必须由 Inbox Item ID 稳定确定性派生，建议：

```text
wf_inbox_<stable digest of inbox item id>
```

同一个 Inbox Item 最多产生一个 Waiting-For；重试必须复用同一 ID；不按文本相似度去重，也不使用 LLM 判断重复。

## Inbox-to-Waiting-For Saga

规划为 `InboxService` 注入 canonical `WaitingForService` 并增加 `resolve_to_waiting_for()`：

```text
claim Inbox resolution as WAITING_FOR
→ reserve deterministic target ID
→ call WaitingForService.create(explicit ID)
→ record TARGET_CREATED
→ complete Inbox resolution
```

Waiting-For metadata 至少记录 `inbox_item_id` 与 `inbox_source`，不得复制敏感 metadata、Workspace 凭据或不必要的原始上下文。

如果目标 ID 已存在，仅当其 `inbox_item_id` 与当前 Inbox Item 一致时允许恢复；其他同 ID 冲突必须失败，不得覆盖已有对象。

`inbox.db` 与 `followups.db` 不提供跨数据库原子事务。恢复继续依靠 `CLAIMED → TARGET_CREATED → COMPLETED`，不建立第二套 Saga 表或转换状态机。

## API 与 CLI 规划

### API

规划新增：

```text
POST /inbox/{item_id}/resolve/waiting-for
```

Request 至少包含 `subject`、`waiting_on`、`context`、`expected_by`、`next_review_at`、`timezone`。Response 继续使用现有 Inbox response contract，返回 resolved Inbox Item，并包含：

```text
resolved_type = waiting_for
resolved_target_id = wf_...
```

不得创建第二种 Inbox Response Contract。

### CLI

规划新增：

```text
python -m cli inbox resolve-waiting-for <INBOX_ID>
```

参数至少包含 `--subject`、`--waiting-on`、`--context`、`--expected-by`、`--next-review-at`、`--timezone`、`--json`。CLI 必须通过 canonical Composition Root 复用 `InboxService`，不得直接调用 Waiting-For Repository。

## CEO Assistant Intent 规划

| Intent | Effect |
|---|---|
| `waiting_for_list` | READ |
| `waiting_for_detail` | READ |
| `waiting_for_history` | READ |
| `waiting_for_capture` | WRITE |
| `waiting_for_confirm` | WRITE |
| `waiting_for_follow_up` | WRITE |
| `waiting_for_snooze` | WRITE |
| `waiting_for_resolve` | WRITE |
| `waiting_for_cancel` | WRITE |
| `waiting_for_reopen` | WRITE |

`_assert_effect_contract()` 必须显式列出每个 intent。禁止 LLM 分类写操作、confidence 阈值自动执行、Chat fallback 自动写入，以及通用“看起来像等待”规则直接创建 Waiting-For。

## 写操作目标识别

follow-up、snooze、resolve、cancel、reopen 必须要求 `wf_...` canonical ID。标题或人名查询只可返回候选列表，不产生写入。

未提供 ID 时，系统返回候选 Waiting-For ID，要求用户明确选择，并保证零写入。

## Revision 与并发

CEO Assistant 执行生命周期写入时：

1. 先通过 `WaitingForService.get()` 读取当前 revision；
2. 使用该 revision 调用 mutation；
3. Repository CAS 仍是最终并发正确性边界；
4. revision conflict 显式返回；
5. 不自动重试写操作；
6. 不追加重复 Event。

成功回复必须包含 Waiting-For ID、new revision、event type，以及 `next_review_at` 或终态 status。LLM 文本不得作为成功证据。

## 用户错误呈现

规划独立或扩展现有 Presenter，提供确定性中文提示，至少覆盖：缺少 Inbox ID、缺少 Waiting-For ID、缺少 `waiting_on`、缺少 `subject`、缺少时间字段、时间超出支持范围、Waiting-For 不存在、Workspace 不匹配、revision conflict、终态不允许催办或延期、Inbox 已转换、Inbox 转换类型冲突、Waiting-For 服务不可用。

Presenter 只转换展示文本，不修改 `FailureInfo.code`、`FailureInfo.category`、HTTP status 或 CLI exit code。

## Daily Agenda 展示

SP-017 不修改 Agenda 聚合规则，只规划 CEO Assistant 展示优化：`waiting_for → 等待事项`。

普通文本至少显示 ID、subject、waiting_on、status、`next_review_at` / `expected_by`，不得展示完整 context 或 resolution_note。Agenda 仍是 read model，不复制 Waiting-For 真相。

## 明确排除

SP-017 不包含：

- LLM side-effect classification 或 LLM entity extraction for writes
- 一步式自然语言 Waiting-For 创建
- 自动 Reminder 或 Scheduler Job
- 外部微信、邮件、短信、Push 或自动向联系人发送催办
- Recurring、Web UI、Background follow-up agent
- Work Log 查询重构、Knowledge
- 多用户身份、RBAC 或跨数据库事务
- SP-018 或 SP-019 内容

## 未来实现工作流

### Workstream A — Inbox Target Extension

- enum 与 claim validation
- `WaitingForService` 注入与 `resolve_to_waiting_for`
- API/CLI
- restart / recovery

### Workstream B — Deterministic Follow-up Intent

- parser 与 effect contract
- read handlers
- capture / confirm handlers
- lifecycle handlers
- error presenter

### Workstream C — Interaction Acceptance

- 真实 CEO Assistant entrypoint
- 真实 CLI/API
- Workspace 隔离
- 重复确认与 crash recovery
- CAS
- Agenda 文本
- 无 LLM 写入

本 RFC 已通过规划 PR #42 采用，并由 SP-017 完成实现、自动化验证、人工验收与治理封存；RFC 状态保持 Adopted。

## 未来验收场景

| 场景 | 必须证明 |
|---|---|
| A | Waiting-For list/detail/history read |
| B | 模糊语句只捕获 Inbox |
| C | Capture 不创建 Waiting-For |
| D | 明确 Inbox 确认只创建一个 Waiting-For |
| E | 确认重试不创建重复对象 |
| F | target 创建后崩溃可正确恢复 |
| G | Workspace 隔离 |
| H | 显式 follow-up/snooze 生命周期 |
| I | resolve/cancel/reopen 生命周期 |
| J | 缺少 ID 时返回候选且零写入 |
| K | 不支持时间时零写入 |
| L | 无 Reminder/Scheduler 副作用 |
| M | Task/Reminder/Work Log/Note/Dismiss Inbox 路径回归 |
| N | CEO Assistant、API、CLI 共享 canonical truth |
| O | LLM 不可用不阻断确定性交互 |
| P | 失败返回稳定 FailureInfo 且无假成功 |
