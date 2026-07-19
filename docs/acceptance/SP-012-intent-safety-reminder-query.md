# SP-012 自然语言意图安全验收

状态：APPROVED / MERGED / RECONCILED / ARCHIVED

## 验收边界

SP-012 已通过 PR #25 合入 `main`，Squash Commit 为
`d550ab8757b50e4d12587d5e71a0058089bd3821`。

本文件不声明一套未执行的独立 SP-012 全量手工验收。SP-012 的查询兼容性由
SP-013 场景 H 实际覆盖；其余场景保留为实现合同和后续专项验收参考。

## 已验证兼容性

SP-013 场景 H 在 Mock Provider、独立数据目录、真实 Composition Root 下输入：

```text
今天都有什么事？
```

实际结果：

- `metadata.intent = reminder_list`
- `metadata.effect = read`
- 未漂移到 `daily_agenda`
- 查询前后 Work Log、UserTask、Reminder 的数量及 ID 集合一致
- 兼容性结论：PASSED

## 原验收计划（未声明独立全量执行）

### 场景 A：今天查询无副作用

输入“今天都有哪些提醒？”等只读问句，预期返回 Reminder 列表，且
`intent=reminder_list`、`effect=read`，查询不写入 Work Log、UserTask 或 Reminder。

### 场景 B：缺少目标

输入“查看提醒”与“取消提醒”，预期返回 `reminder.target_required` 和中文操作示例，
不产生写入。

### 场景 C：不支持时间

输入“30分钟后提醒我开会”，预期返回 `reminder.time_unsupported`，并仅提示当前
Parser 已支持的明确时间格式。

### 场景 D：合法工作记录

输入“记录一下今天完成了报价审核”，预期只新增一条 Work Log，且
`metadata.effect=write`。

### 场景 E：Mock 噪音

Reminder 查询与错误引导不得出现 `MOCK MODE`、API Key 或 Provider 配置提示；
普通 Chat 保持既有 Mock 提示合同。
