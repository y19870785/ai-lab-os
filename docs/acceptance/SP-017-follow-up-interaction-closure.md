# SP-017 Follow-up Interaction & Capture Closure 验收记录

状态：LOCAL_AUTOMATED_VERIFICATION_PASSED / MANUAL_ACCEPTANCE_PASSED / PR_QUALITY_GATE_PASSED / POST_MERGE_QUALITY_GATE_PASSED / INDEPENDENT_REVIEW_APPROVED / FINAL

本地验收日期：2026-07-23（Asia/Shanghai）

Feature PR：#43

Approved Head：`40319102eb7aaea90a24d8abdf106e406b680618`

Feature Merge Commit：`32bb9c0a939c65f2278fc2b6be8d072fb2e3656a`

Merged At：`2026-07-23T12:25:57Z`

PR Quality Gate Run：`30006130019`

Post-Merge main Quality Gate Run：`30006958413`

Post-Merge main Quality Gate：Ruff `SUCCESS`；pytest (non-real) `SUCCESS`（`1239 passed, 6 skipped, 27 warnings`）

Independent Review：`APPROVED`

ACC-017 A～O：PASSED / FINAL

首次内联验收因 PowerShell 管道未显式使用 UTF-8，中文输入被替换为 `?`，归类为 `INVALID_ACCEPTANCE_HARNESS`，不计作产品失败。显式设置 UTF-8 后重新从真实入口执行，A～O 全部通过。

## 固定边界

- 自然语言创建只能走 `Inbox capture -> Inbox ID confirm -> InboxService.resolve_to_waiting_for()`。
- Lifecycle mutation 必须使用 canonical `wf_...` ID。
- 不使用 LLM 判断写 Intent、补猜字段或证明成功。
- 复用 `inbox_resolution_claims` 的 `CLAIMED -> TARGET_CREATED -> COMPLETED`；无新表、无第二套 Saga。
- 产品版本保持 `0.34.0`，不修改 Tag、Release 或发布授权。

## 自动化覆盖

| 场景 | 自动化证据 | 当前状态 |
|---|---|---|
| ACC-017-A 只读列表 | `test_waiting_for_capture_confirm_read_and_lifecycle_are_deterministic` | COVERED |
| ACC-017-B 模糊捕获 | 同上；验证只增加 pending Inbox | COVERED |
| ACC-017-C 确认创建 | 同上；验证 `wf_inbox_...` 与 created event | COVERED |
| ACC-017-D 重复确认 | `test_resolve_to_waiting_for_is_idempotent_and_preserves_source` | COVERED |
| ACC-017-E 类型竞争 | 现有 resolution-claim 竞争回归 + Waiting-For external target | COVERED |
| ACC-017-F 缺失字段 | `test_missing_waiting_for_fields_fail_before_claim_or_target` | COVERED |
| ACC-017-G 时间范围 | `test_waiting_for_time_parser_reuses_supported_subset_and_fails_closed` | COVERED |
| ACC-017-H Lifecycle ID 边界 | CEO Assistant 端到端测试的模糊候选与显式 ID mutation | COVERED |
| ACC-017-I Revision 冲突 | `test_waiting_for_revision_conflict_is_not_retried` | COVERED |
| ACC-017-J 崩溃恢复 | `test_waiting_for_resolution_recovers_each_saga_interruption` 三个阶段 | COVERED |
| ACC-017-K 跨进程竞争 | `test_two_processes_confirm_one_inbox_into_one_waiting_for` | COVERED |
| ACC-017-L Workspace 隔离 | Core/API Waiting-For resolve workspace tests | COVERED |
| ACC-017-M API / CLI 一致性 | 共享 Composition Root、SQLite 与 API/CLI 专项 | COVERED |
| ACC-017-N LLM 无副作用 | `test_waiting_for_agenda_label_and_chat_fallback_have_no_side_effect` | COVERED |
| ACC-017-O Agenda 展示 | 同上；验证等待事项、ID、waiting_on 且不泄露 context | COVERED |

## 手工验收矩阵

以下场景已使用隔离数据目录、真实 API/CLI/CEO Assistant 入口执行。CLI 首次确认与重复确认均返回 `wf_inbox_7cf3a4fd23a28c1e7835df22`；Waiting-For 数量为 1，created event 数量为 1。

### ACC-017-A：只读列表

输入 `查看等待事项`；记录操作前后 Inbox、Waiting-For 与 Event ID 集合，必须零写入。

### ACC-017-B：模糊捕获

输入 `等张经理回复蜂蜡检测方案`；必须只创建 `suggested_type=waiting_for` 的 pending Inbox，并返回 Inbox ID。

### ACC-017-C：确认创建

使用 B 的 Inbox ID 输入 `把 inbox_x 整理成等待事项：等待张经理回复蜂蜡检测方案，明天下午三点再看`；必须得到唯一 `wf_...`、正确来源 metadata 与 created event。

### ACC-017-D：重复确认

重复 C；必须返回相同 ID，且 Waiting-For 数量与 created event 数量不增加。

### ACC-017-E：类型竞争

先把 Inbox 转成 Note 或其他类型，再尝试 Waiting-For；必须返回类型冲突并保持原状态。

### ACC-017-F：缺失字段

缺少 `waiting_on` 或时间确认；必须返回明确 `missing_fields` 与可复制模板，Inbox 保持 pending。

### ACC-017-G：时间范围

`明天下午三点` 必须成功；`下周有空时` 必须 fail closed 且零 Waiting-For 写入。

### ACC-017-H：Lifecycle ID 边界

不含 `wf_...` ID 的模糊 mutation 不进入 Waiting-For lifecycle mutation；使用显式 `wf_...` ID 后 mutation 成功并增加 revision/event。

### ACC-017-I：Revision 冲突

旧 revision 必须明确冲突，不自动重试，不追加 event。

### ACC-017-J：崩溃恢复

分别在 CLAIMED 后、目标创建后、TARGET_CREATED 后中断；重试必须完成同一 Inbox 与同一目标。

### ACC-017-K：跨进程竞争

两个独立 CLI 进程确认同一 Inbox；最终只能存在一个目标。

### ACC-017-L：Workspace 隔离

Workspace B 不得读取、确认或修改 Workspace A 的 Inbox/Waiting-For。

### ACC-017-M：API / CLI 一致性

API 转换后 CLI 读取同一对象；CLI mutation 后 API 读取同一 revision/event。

### ACC-017-N：LLM 无副作用

普通 Chat/LLM fallback 前后 Inbox、Waiting-For 与 Event 集合不变。

### ACC-017-O：Agenda 展示

显示“等待事项”、ID、subject、waiting_on 与时间；不显示完整 context、resolution_note 或敏感 metadata。

## 手工验收结果

| 场景 | 结果 | 证据摘要 |
|---|---|---|
| A | PASSED | 列表前后 Inbox、Waiting-For、Event 计数不变 |
| B | PASSED | 只新增 pending Inbox，`suggested_type=waiting_for` |
| C | PASSED | 创建唯一 `wf_inbox_...` 与 created event |
| D | PASSED | 重复确认返回同一 ID，目标与 event 数不增加 |
| E | PASSED | Note 后 Waiting-For 转换返回 `inbox.already_resolved` |
| F | PASSED | 返回 missing fields 与 confirmation template，Inbox 保持 pending |
| G | PASSED | 明天下午三点成功；下周有空时返回 `waiting_for.time_unsupported` 且零目标写入 |
| H | PASSED | 模糊 mutation 不进入 Waiting-For lifecycle；显式 ID resolve 成功 |
| I | PASSED | 旧 revision 返回 409，event 数不增加 |
| J | PASSED | CLAIMED、target-created-unrecorded、TARGET_CREATED 三阶段恢复均只保留一个目标 |
| K | PASSED | 两个独立 CLI 进程返回同一 ID，最终只有一个目标 |
| L | PASSED | Workspace B 确认 Workspace A Inbox 返回 403 |
| M | PASSED | API 创建后 CLI 读取到同一 Waiting-For ID |
| N | PASSED | Chat fallback 前后 Inbox、Waiting-For、Event 计数不变 |
| O | PASSED | Agenda 显示等待事项、ID、waiting_on；不显示完整 context |
