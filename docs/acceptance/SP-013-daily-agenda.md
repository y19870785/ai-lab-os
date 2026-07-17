# SP-013 Daily Agenda Manual Acceptance

Status: SP-013 implementation candidate / Awaiting ChatGPT review / Not merged

## Environment
- Mock Provider
- Temporary data directory
- Asia/Shanghai timezone
- Reminders and Scheduler enabled

## Scenarios

### A: Today
Create today and tomorrow reminders. Verify today view returns only today items. No write side effects.

### B: Next 3 Hours
Create reminders at +1h, +2h, +5h. Verify next/3 returns only the first two.

### C: Attention
Create 1 overdue task, 1 failed reminder, 1 normal reminder. Verify attention returns only the overdue/failed items.

### D: Completed
Create today work log and yesterday work log. Verify completed returns today only.

### E: No Side Effects
All agenda queries leave UserTask, Reminder, and WorkLog counts unchanged.

### F: Restart
Restart API with same data directory. Agenda results remain consistent.

### G: Natural Language
Verify today/next/attention/completed intent routing with read effect and no Mock noise.

### H: SP-012 Compatibility
Verify "today" queries still route to reminder_list/read.
