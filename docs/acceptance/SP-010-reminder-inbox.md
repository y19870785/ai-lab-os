# SP-010 Reminder Inbox 本地验收

## 前提

在仓库根目录打开 PowerShell。以下验收使用 Mock Provider，不需要真实模型 Key，不会发送外部通知。

```powershell
$env:AI_LAB_PROVIDER_MODE = "mock"
$env:AI_LAB_ENABLE_USER_TASKS = "true"
$env:AI_LAB_ENABLE_REMINDERS = "true"
$env:AI_LAB_ENABLE_SCHEDULER = "true"
$env:AI_LAB_TIMEZONE = "Asia/Shanghai"
$env:AI_LAB_API_AUTH_ENABLED = "true"
$env:AI_LAB_API_TOKEN = "local-sp010-token"
```

## 启动 API

```powershell
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

在另一个 PowerShell 窗口复用上述环境变量，然后创建距离当前约两分钟的提醒：

```powershell
$target = (Get-Date).AddMinutes(2)
$day = if ($target.Date -eq (Get-Date).Date) { "今天" } else { "明天" }
$phrase = "$day $($target.ToString('HH:mm')) 提醒我联系张经理确认蜂蜡检测方案"
$headers = @{ Authorization = "Bearer local-sp010-token" }
$created = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" `
  -Headers $headers -ContentType "application/json; charset=utf-8" `
  -Body (@{ user_input = $phrase } | ConvertTo-Json)
$created.metadata | Format-List
```

输出应包含真实 `task_id`、`reminder_id`、`scheduler_job_id`、`scheduled_for` 与 `scheduled` 状态。

再准备一条较远的 scheduled Reminder 和一条 cancelled Reminder：

```powershell
$tomorrow = (Get-Date).AddDays(1).ToString("yyyy-MM-dd")
$future = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" `
  -Headers $headers -ContentType "application/json; charset=utf-8" `
  -Body ([Text.Encoding]::UTF8.GetBytes((@{ user_input = "明天下午3点提醒我整理报价" } | ConvertTo-Json)))
$toCancel = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" `
  -Headers $headers -ContentType "application/json; charset=utf-8" `
  -Body ([Text.Encoding]::UTF8.GetBytes((@{ user_input = "明天下午4点提醒我取消验收" } | ConvertTo-Json)))
Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:8000/reminders/$($toCancel.metadata.reminder_id)" -Headers $headers
```

## 查询 Inbox

```powershell
$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/reminders?status=scheduled" -Headers $headers
$response.Headers["Content-Type"]
$inbox = $response.Content | ConvertFrom-Json
$inbox.items | Format-Table status, scheduled_for, task_title, reminder_id
```

`Content-Type` 必须包含 `application/json` 与 `charset=utf-8`，中文标题必须可读。也可查询：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/reminders?time_scope=today" -Headers $headers
Invoke-RestMethod -Uri "http://127.0.0.1:8000/reminders?time_scope=upcoming&limit=10&offset=0" -Headers $headers
Invoke-RestMethod -Uri "http://127.0.0.1:8000/reminders?status=cancelled" -Headers $headers
```

本机 Windows PowerShell `5.1.26100.8737` 已实际验证上述 UTF-8 byte body 与 `Invoke-WebRequest` 查询：响应为 `application/json; charset=utf-8`，中文 `task_title` 正常显示。PowerShell 7 未安装，因此本记录不声称验证了 PowerShell 7；当前推荐使用这里经过验证的 PowerShell 5.1 命令。`curl.exe` 或 Python 可作为客户端排障工具，但不替代本验收记录。

## 重启与到期

停止 API，使用相同数据目录和环境变量重新启动。再次执行 Inbox 查询，记录必须仍存在。到期后查询：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/reminders?status=triggered" -Headers $headers
Invoke-RestMethod -Uri "http://127.0.0.1:8000/reminders/$($created.metadata.reminder_id)/occurrences" -Headers $headers
```

目标 Reminder 应为 `triggered`，Occurrence 恰好一条。

## CLI 查询

```powershell
python -m cli reminders --upcoming
python -m cli reminders --status triggered --json
```

CLI 与 API 必须显示相同的持久化 Reminder ID、状态、时间与中文标题，并在退出前正常关闭 SystemContainer。

## 验收标准

- 不需要预先知道 Reminder ID 即可列出记录；
- `today` 使用 `Asia/Shanghai` 自然日，`upcoming` 从当前 UTC 时刻换算；
- 分页返回当前页 `count` 与准确 `has_more`；
- 重启后列表仍存在；
- 到期状态与单条状态、Occurrence 一致；
- 数据集中至少包含一条 scheduled、一条 triggered 和一条 cancelled Reminder；
- 没有外部通知、Recurring Reminder 或 Web UI 预期。
