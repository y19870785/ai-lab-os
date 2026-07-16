# SP-009 Natural-Language Reminder Closure Acceptance

This Windows PowerShell procedure validates the in-app product result. It uses explicit mock provider mode; no external notification is expected.

## Configure An Isolated Local Runtime

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

## Start The API

```powershell
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Keep that terminal open. In a second PowerShell terminal, set the same environment variables and prepare headers:

```powershell
$headers = @{
  Authorization = "Bearer $env:AI_LAB_API_TOKEN"
  "Idempotency-Key" = "sp009-manual-001"
}
```

## Create A Reminder Due In One Or Two Minutes

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

Task due dates and Reminder scheduling are separate. For example, `添加任务：明天下午3点联系张经理` creates a UserTask with `due_at`, but creates no Reminder or Scheduler Job. A Reminder phrase must contain a supported future time. Independent requests may omit `Idempotency-Key` and receive distinct chains; retries that must reuse a chain should send the same explicit key.

The response must contain `task_id`, `reminder_id`, `scheduler_job_id`, `scheduled_for`, `timezone`, and `reminder_status=scheduled`.

## Query The In-App Status

```powershell
Invoke-RestMethod -Headers $headers `
  -Uri "http://127.0.0.1:8000/reminders/$reminderId/status" | Format-List

python -m cli reminder-status $reminderId
```

## Restart Persistence Check

Stop Uvicorn with Ctrl+C, run the same startup command again, then repeat the status query. The same Reminder must still be `scheduled` or already `triggered`; its IDs must not change.

## Due-Time And Effectively-Once Check

After the due time:

```powershell
$status = Invoke-RestMethod -Headers $headers `
  -Uri "http://127.0.0.1:8000/reminders/$reminderId/status"
$occurrences = Invoke-RestMethod -Headers $headers `
  -Uri "http://127.0.0.1:8000/reminders/$reminderId/occurrences"
$status | Format-List
$occurrences | Format-Table
```

## Acceptance Criteria

- UserTask, Reminder, and Scheduler Job IDs are returned and persisted.
- Restart preserves the scheduled chain.
- At due time the aggregate status becomes `triggered`.
- Exactly one `ReminderOccurrence` is returned after repeated queries and another restart.
- A failed execution is shown as `retrying` or `failed`, never as `triggered`.
- No email, WeChat, SMS, popup, or other external notification is expected.
- SQLite does not need to be opened manually to determine success.
