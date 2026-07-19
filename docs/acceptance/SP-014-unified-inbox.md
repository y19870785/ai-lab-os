# SP-014 Unified Inbox 手工验收

Status: DRAFT / IMPLEMENTATION_CANDIDATE

本文件定义验收步骤，不预先声明任何场景已通过。所有 PASSED 结论必须来自实际执行与可复核证据。

## 环境

```powershell
$env:AI_LAB_DATA_DIR = "$PWD\data\sp014-manual-acceptance"
$env:AI_LAB_SQLITE_DIR = "$env:AI_LAB_DATA_DIR\sqlite"
$env:AI_LAB_PROVIDER_MODE = "mock"
$env:AI_LAB_ENABLE_REMINDERS = "true"
$env:AI_LAB_ENABLE_SCHEDULER = "true"
$env:AI_LAB_TIMEZONE = "Asia/Shanghai"
$env:AI_LAB_API_AUTH_ENABLED = "false"
$env:PYTHONIOENCODING = "utf-8"
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

不得配置或调用真实模型密钥。每个 read 场景执行前后记录 InboxItem、UserTask、Reminder、Work Log 的数量和 ID 集合。

## A — Capture

输入 CEO Assistant：

```text
记一下，下周和包装供应商确认新版瓶盖
```

预期：`metadata.intent=inbox_capture`、`metadata.effect=write`；创建一个 `source=ceo_assistant` 的 pending InboxItem；不创建 Task、Reminder 或 Work Log；确定性响应中没有 Mock/API Key 噪音。

## B — List

输入：

```text
看看我的收件箱
```

并交叉检查：

```powershell
python -m cli inbox list --json
Invoke-RestMethod http://127.0.0.1:8000/inbox
```

预期：只返回 pending 项目，`metadata.intent=inbox_list`、`metadata.effect=read`，调用前后四类对象的数量与 ID 集合完全一致。

## C — Resolve to Task

```powershell
python -m cli inbox resolve-task <ITEM_ID> --title "确认新版瓶盖" --priority medium --json
```

预期：创建真实 UserTask；InboxItem 变为 `resolved/user_task`，`resolved_target_id` 指向该 Task；Daily Agenda 可看到目标 Task。重复执行返回 `inbox.already_resolved`，Task 数量和 ID 集合不增加。

## D — Resolve to Reminder

先通过 API 或 CLI 捕获另一条记录，再执行：

```powershell
python -m cli inbox resolve-reminder <ITEM_ID> --title "联系包装供应商" --scheduled-at "<带时区 ISO 时间>" --timezone "Asia/Shanghai" --json
```

预期：通过既有 Reminder orchestration 创建 Reminder；InboxItem 记录真实 Reminder ID；现有 Reminder 查询可见。不得直接写 Reminder 表。

## E — Resolve as Note

```powershell
python -m cli inbox resolve-note <ITEM_ID> --json
```

预期：InboxItem 为 `resolved/note`，`resolved_target_id=null`；Task、Reminder、Work Log 数量和 ID 集合不变。

## F — Dismiss

```powershell
python -m cli inbox dismiss <ITEM_ID> --json
python -m cli inbox list --json
python -m cli inbox list --status all --json
```

预期：项目状态为 dismissed；默认 pending 列表不再显示，all 列表仍可追踪；原始记录未删除，未创建任何目标对象。

## G — Restart

记录所有 Inbox Item 的 ID、状态、解析类型与目标 ID，停止 Uvicorn，再以相同数据目录重启并重复查询。

预期：pending/resolved/dismissed 状态和 `resolved_target_id` 保持一致；目标对象数量与 ID 集合不变；不重复创建目标对象。

## H — Compatibility

逐条输入：

```text
提醒我明天下午三点联系客户
记录一下今天完成了包装验货
创建任务：跟进客户
今天都有什么事？
查看今日日程
我们聊聊明年的方向
```

预期依次保持 Reminder/UserTask 创建路径、Work Log、UserTask、`reminder_list/read`、`daily_agenda/read`、普通 Chat；均不得漂移到 Inbox。执行前后检查 Inbox ID 集合，只有明确 Inbox capture 表达才允许新增。

## 通过标准

A～H 均实际执行通过；workspace 隔离、重复解析、重启持久化和 read-only 无副作用均有证据；未调用真实模型，未出现未解释写入。
