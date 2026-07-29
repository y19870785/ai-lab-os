# SP-013 Daily Agenda 人工验收

Status: APPROVED / MERGED / MANUAL_ACCEPTANCE_PASSED

## Final Acceptance

- Automated acceptance: PASSED
- Code review: APPROVED
- Merge: COMPLETED
- Manual product acceptance: PASSED
- Final result: PASSED
- Product version: `0.33.0`
- Tag / Release: absent

## GitHub Baselines

- SP-013 feature: PR #27, Squash Commit
  `67c5ea922a1a6bd935a3c7c31e43fd83e3d32aa1`
- SP-013 post-merge reconciliation: PR #28, merge commit
  `1b4285efa483e5a389cd0055f3e053ccc7a6f25e`
- SP-013B Daily Agenda CLI workspace fix: PR #29, Squash Commit
  `23b54be4bd3030c564c2e1a0325eaf36199357fe`
- CI-001 Quality Gate: PR #30, Squash Commit
  `7750b1ebd2cc6f937496c904bf1d482952b1b52c`

## 验收环境

- Python 3.12。
- Mock Provider；不使用真实模型密钥。
- 独立数据目录。
- `Asia/Shanghai`
- 启用 Reminders 与 Scheduler。
- 仅在隔离的本地验收 Harness 中显式禁用 API auth。
- 不直接操作 SQLite。

## Scenario Results

| Scenario | Result | Verified outcome |
|---|---|---|
| A — Today | PASSED | Today items included; tomorrow items excluded; read-only |
| B — Next 3 Hours | PASSED | +1h/+2h included; +5h excluded; read-only |
| C — Attention | PASSED | Overdue UserTask and failed Reminder included; normal Reminder excluded |
| D — 已完成 | PASSED | 包含已触发 Reminder 和今日 Work Log；排除昨日 Work Log 与未完成 Task |
| E — No Side Effects | PASSED | UserTask, Reminder and Work Log counts and ID sets unchanged |
| F — 重启 | PASSED | 重启后同一数据目录保留议程标识与聚合状态 |
| G — 自然语言 | PASSED | Daily Agenda 输入返回 `daily_agenda/read`，且没有 Provider 噪声 |
| H — SP-012 Compatibility | PASSED | “今天都有什么事？” remained `reminder_list/read` with no writes |

## SP-013C C / D Retest

The final retest ran on `main` commit
`23b54be4bd3030c564c2e1a0325eaf36199357fe` with freshly seeded, date-correct
isolated data.

Commands:

```powershell
python -m cli agenda --attention --json
python -m cli agenda --completed --json
```

Both commands exited with code `0`; neither emitted `agenda.query_failed`.

### C — Attention

- Included overdue UserTask `ut_374ff65a05ed4db788a3d48462507899`
- Included failed Reminder `rem_cc66b86aaac542228386f1f13fe680db`
- Excluded normal scheduled Reminder `rem_e442d5b6ea9f49a88b71fc3bbf3304ca`

### D — Completed

- Included triggered Reminder `rem_b119ad07e86e419c8beeeeb272e8dc6f`
- Included today's Work Log `f2baefe6718a474fb12ef79de639048d`
- Excluded yesterday's Work Log `407a69b0d9f342e9afd7063c3d2170a0`
- Excluded unfinished UserTask `ut_4bd6f2d2ff3f46c68b5ecf2750aab161`

For both reads, the before/after snapshots were identical:

- UserTask: 10 objects, same ID set
- Reminder: 8 objects, same ID set
- Work Log: 2 objects, same ID set

## Quality Gate Baselines

GitHub Ubuntu Quality Gate after SP-013B merge:

```text
1096 passed, 6 skipped, 27 warnings
Ruff: SUCCESS (changed Python files only)
```

The six skipped tests are Windows-only batch-script tests. The Windows local baseline is:

```text
1102 passed, 5 deselected
```

SP-013C 对账重新执行了要求的显式 ignore 命令：

```text
python -m pytest tests --ignore=tests/real -m "not real" -q --tb=no
1102 passed, 27 warnings
Exit code: 0
```

显式 `--ignore=tests/real` 会阻止这些测试进入收集阶段，因此该次运行不会报告五个由 marker 取消选择的测试。平台统计与命令范围统计互为补充，并不冲突；此处不声称获得任何真实 Provider 结果。
