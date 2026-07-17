# SP-012 自然语言意图安全验收

状态：SP-012 implementation candidate / Draft PR / Awaiting ChatGPT review / Not merged

## 环境

使用临时数据目录、显式 Mock Provider、启用 Reminder 与 Scheduler 的真实 Composition Root。不得读取真实 API Key，也不得把自动测试冒充用户验收。

## 场景 A：今天查询无副作用

依次输入：

```text
今天都有什么事？
今天都有哪些提醒？
我今天有什么要做的？
```

确认返回 Reminder 列表，且查询前后 Work Log、UserTask 与 Reminder 数量均不变。响应 metadata 的 `intent` 为 `reminder_list`、`effect` 为 `read`。

## 场景 B：缺少目标

输入 `查看提醒` 与 `取消提醒`。确认返回 `reminder.target_required` 和中文操作示例，不产生写入。

## 场景 C：不支持时间

输入 `30分钟后提醒我开会`。确认返回 `reminder.time_unsupported`，中文提示只列出当前 Parser 已支持的今天/明天明确时间格式。

## 场景 D：合法工作记录

输入 `记录一下今天完成了报价审核`。确认只新增一条 Work Log，且 metadata 的 `effect` 为 `write`。

## 场景 E：Mock 噪音

所有 Reminder 查询与错误引导均不得出现 `MOCK MODE`、API Key 或 Provider 配置提示；普通 Chat 保持既有 Mock 提示合同。
