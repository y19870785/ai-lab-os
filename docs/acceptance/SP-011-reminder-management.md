# SP-011 Reminder Management 手工验收

**Implementation status:** Merged through PR #23.
**Manual product acceptance:** Pending.

本验收使用本地 Mock Provider、真实 FastAPI lifespan、真实 Composition Root、真实 SQLite 与 Scheduler。它不会调用真实 LLM，也不会修改系统编码。

## 1. PowerShell 环境

```powershell
$env:AI_LAB_PROVIDER_MODE = "mock"
$env:AI_LAB_ENABLE_REMINDERS = "true"
$env:AI_LAB_ENABLE_SCHEDULER = "true"
$env:AI_LAB_TIMEZONE = "Asia/Shanghai"
$env:AI_LAB_API_AUTH_ENABLED = "true"
$env:AI_LAB_API_TOKEN = "local-sp011-token"
$env:AI_LAB_DATA_DIR = "$PWD\data\sp011-acceptance"
$env:AI_LAB_SQLITE_DIR = "$env:AI_LAB_DATA_DIR\sqlite"
$headers = @{ Authorization = "Bearer $env:AI_LAB_API_TOKEN" }
```

启动 API：

```powershell
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

另开一个 PowerShell 窗口并重新设置 `$headers` 后执行后续步骤。

## 2. 场景 A：Pending Inbox

用距离当前时间 2 至 5 分钟的受支持表达创建两条提醒：

```powershell
$a = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -Headers $headers -ContentType "application/json; charset=utf-8" -Body (@{ user_input = "今天 23:55 提醒我整理报价" } | ConvertTo-Json)
$b = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -Headers $headers -ContentType "application/json; charset=utf-8" -Body (@{ user_input = "今天 23:56 提醒我联系张经理" } | ConvertTo-Json)
$a.metadata
$b.metadata
```

请将示例时间替换为当天尚未过去的明确时间。取消第二条并查询 pending：

```powershell
Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:8000/reminders/$($b.metadata.reminder_id)" -Headers $headers
Invoke-RestMethod -Uri "http://127.0.0.1:8000/reminders?view=pending" -Headers $headers
Invoke-RestMethod -Uri "http://127.0.0.1:8000/reminders?status=cancelled&time_scope=upcoming" -Headers $headers
```

验收：pending 仅包含 scheduled/retrying 且时间未到的记录；显式 cancelled + upcoming 仍能找到第二条。

## 3. 场景 B：取消后不触发

```powershell
python -m cli reminder-cancel $b.metadata.reminder_id --json
python -m cli reminder-status $b.metadata.reminder_id --human
```

等待原时间后：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/reminders/$($b.metadata.reminder_id)/occurrences" -Headers $headers
```

验收：状态为 `cancelled`，Scheduler Job 不再执行，Occurrence 数量为 0；重复取消仍返回 cancelled。

## 4. 场景 C：改期与重启

为第一条选择一个新的未来 ISO-8601 时间：

```powershell
$newTime = "2026-07-18T16:00:00+08:00"
$body = @{ scheduled_for = $newTime; timezone = "Asia/Shanghai" } | ConvertTo-Json
Invoke-RestMethod -Method Patch -Uri "http://127.0.0.1:8000/reminders/$($a.metadata.reminder_id)" -Headers ($headers + @{ "Idempotency-Key" = "sp011-reschedule-a" }) -ContentType "application/json" -Body $body
python -m cli reminder-reschedule $a.metadata.reminder_id --scheduled-for $newTime --timezone Asia/Shanghai --idempotency-key sp011-reschedule-a --json
```

请把 `$newTime` 改为实际验收时仍在未来的时间。停止 API，使用同一环境变量重新启动，再查询：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/reminders/$($a.metadata.reminder_id)/status" -Headers $headers
```

验收：Reminder ID、Task 关联和 Scheduler Job ID 保持一致；新时间持久化；旧时间不触发；新时间到期后状态为 `triggered` 且 Occurrence 恰好 1 条。

## 5. 场景 D：确定性自然语言

```powershell
$queries = @(
  "查看我的提醒",
  "查看待处理提醒",
  "查看提醒 $($a.metadata.reminder_id)",
  "取消提醒 $($b.metadata.reminder_id)"
)
foreach ($query in $queries) {
  Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -Headers $headers -ContentType "application/json; charset=utf-8" -Body (@{ user_input = $query } | ConvertTo-Json)
}
```

验收：回答中不出现 `MOCK MODE`、`OPENAI_API_KEY` 或 `real LLM`。普通 LLM Chat 在 Mock 模式下仍可明确显示 Mock 提示。

## 6. 场景 E：Windows CLI UTF-8

不要设置永久 `PYTHONIOENCODING`。直接捕获中文 JSON：

```powershell
python -m cli reminders --pending --json | Set-Content -Encoding utf8 .\sp011-reminders.json
Get-Content .\sp011-reminders.json -Encoding utf8 | ConvertFrom-Json
Remove-Item .\sp011-reminders.json
```

验收：中文标题可读，JSON 可解析，stdout 没有日志污染，诊断只进入 stderr。

## 验收边界

本轮不期待外部通知、系统弹窗、Recurring Reminder、Web UI、批量操作、模糊语义搜索、用户身份或 RBAC。Reminder 与 Scheduler 跨 SQLite 协调仍是可恢复 Saga，不是单数据库原子事务。
