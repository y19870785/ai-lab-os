# SP-009 自然语言 Reminder 闭环验收

以下 Windows PowerShell 流程验证站内产品结果。流程显式使用 Mock Provider，不预期任何
外部通知。

## 配置隔离的本地 Runtime

```powershell
$env:AI_LAB_PROVIDER_MODE = "mock"
$env:AI_LAB_ENABLE_USER_TASKS = "true"
$env:AI_LAB_ENABLE_SCHEDULER = "true"
$env:AI_LAB_ENABLE_REMINDERS = "true"
$env:AI_LAB_TIMEZONE = "Asia/Shanghai"
$env:AI_LAB_API_AUTH_ENABLED = "true"
$env:AI_LAB_API_TOKEN = "local-sp009-test-token"
$env:AI_LAB_DATA_DIR = "$PWD\data\sp009-acceptance"
$env:AI_LAB_SQLITE_DIR = "$env:AI_LAB_DATA_DIR\sqlite"
```

## 启动 API

```powershell
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

保持该终端运行。在第二个 PowerShell 终端设置相同环境变量并准备 Header：

```powershell
$headers = @{
  Authorization = "Bearer $env:AI_LAB_API_TOKEN"
  "Idempotency-Key" = "sp009-manual-001"
}
```

## 创建一至两分钟后到期的 Reminder

```powershell
$target = (Get-Date).AddMinutes(2)
$day = if ($target.Date -eq (Get-Date).Date) { "今天" } else { "明天" }
$phrase = "$day $($target.ToString('HH:mm')) 提醒我联系张经理确认蜂蜡检测方案"
$created = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" `
  -Headers $headers -ContentType "application/json; charset=utf-8" `
  -Body (@{ user_input = $phrase } | ConvertTo-Json)
$created.metadata | Format-List
$reminderId = $created.metadata.reminder_id
```

Task due date 与 Reminder schedule 是不同维度。例如
`添加任务：明天下午3点联系张经理` 只创建带 `due_at` 的 UserTask，不创建 Reminder 或
Scheduler Job。Reminder 表达必须包含受支持的未来时间。独立请求可以省略
`Idempotency-Key` 并获得不同链路；需要复用链路的 Retry 应发送同一显式 Key。

响应必须包含 `task_id`、`reminder_id`、`scheduler_job_id`、`scheduled_for`、
`timezone` 与 `reminder_status=scheduled`。

API JSON 响应显式声明 `application/json; charset=utf-8`。若本地 PowerShell 中文显示
异常，先检查 Response `Content-Type`，不得在本次验收中修改系统 Code Page 或 `.env`。
SP-010 的列表验证命令见 `SP-010-reminder-inbox.md`。

## 查询站内状态

```powershell
Invoke-RestMethod -Headers $headers `
  -Uri "http://127.0.0.1:8000/reminders/$reminderId/status" | Format-List

python -m cli reminder-status $reminderId
```

## 重启持久化检查

使用 Ctrl+C 停止 Uvicorn，再执行同一启动命令并重复状态查询。同一个 Reminder 必须仍为
`scheduled` 或已变为 `triggered`，且 ID 不得改变。

## 到期时间与 Effectively-once 检查

到期后执行：

```powershell
$status = Invoke-RestMethod -Headers $headers `
  -Uri "http://127.0.0.1:8000/reminders/$reminderId/status"
$occurrences = Invoke-RestMethod -Headers $headers `
  -Uri "http://127.0.0.1:8000/reminders/$reminderId/occurrences"
$status | Format-List
$occurrences | Format-Table
```

## 验收标准

- 返回并持久化 UserTask、Reminder 与 Scheduler Job ID；
- 重启后保留计划链路；
- 到期时聚合状态变为 `triggered`；
- 重复查询并再次重启后，只返回一个 `ReminderOccurrence`；
- 执行失败显示为 `retrying` 或 `failed`，不得显示为 `triggered`；
- 不预期 Email、WeChat、SMS、Popup 或其他外部通知；
- 无需人工打开 SQLite 即可判断成功。
