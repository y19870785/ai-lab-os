# 版本兼容性矩阵

**Product Version:** `0.33.0`

**Latest Release:** unchanged

**SP-008:** merged into main through PR #16 (`1858d4991379058948559cc96e2672df44e42b67`)

**SP-009:** APPROVED / MERGED / RECONCILED / ARCHIVED through PR #19 (`b1274d066cbc01053144cba8d5654a5f8c8a21da`)

**SP-010:** APPROVED / MERGED / RECONCILED / ARCHIVED through PR #21 (`af437afc32dcb17da68d600d6840ec94c8cbe681`)

**SP-012:** Unreleased APPROVED / MERGED / RECONCILED / ARCHIVED

**SP-011:** APPROVED / MERGED / RECONCILED / ARCHIVED through PR #23 (`5c4b442b2b5c7f934ac381020ba8b310976d5d3a`)

**Main Baseline:** `5c4b442b2b5c7f934ac381020ba8b310976d5d3a`

| Capability | Contract | Minimum AI-Lab baseline |
|---|---|---|
| Reminder Inbox | RFC-020 Adopted / ADR-041 and ADR-042 Accepted | Unreleased (`post-v0.33.0` main) |
| Reminder Management | RFC-021 Adopted / ADR-043/044/045 Accepted | Unreleased (`post-v0.33.0` main); merged through PR #23 |

**Release Tag:** none

**GitHub Release:** none

| Module | Version | Min AI-Lab | Dependencies |
|--------|---------|------------|--------------|
| Core (Bus) | 1.0 | v0.7.0 | - |
| Core (Database) | 1.0 | v0.13.0 | - |
| Memory | 1.0 | v0.13.0 | Core |
| Knowledge | 1.0 | v0.16.0 | Provider, Memory |
| Provider | 1.0 | v0.15.0 | Core |
| Agent Runtime | 1.0 | v0.17.0 | Memory, Knowledge, Provider |
| Tool Runtime | 1.0 | v0.18.0 | Provider |
| MCP Adapter | 1.0 | v0.19.0 | Tool Runtime |
| Workflow Engine | 1.0 | v0.20.0 | Agent, Tool, Memory |
| Scheduler Runtime | 1.0 | v0.21.0 | Workflow, Memory |
| Task Runtime | 1.0 | v0.22.0 | Scheduler, Workflow |
| UserTask | 1.0 | Unreleased（post-v0.33.0 main） | DatabaseManager, EventBus |
| Reminder Bridge | 1.0 | Unreleased（post-v0.33.0 main） | UserTask, Scheduler, DatabaseManager |
| Natural-Language Reminder Closure | 1.0 | Unreleased（post-v0.33.0 main） | CEO Assistant, UserTask, Reminder Bridge, Scheduler |
| Intent Safety and Reminder Query UX | 1.0 | Unreleased（SP-012 branch only） | CEO Assistant, Reminder Inbox, FailureInfo |

## 升级说明

- v0.15.0 → v0.16.0: Knowledge Layer 新增，不影响已有模块
- v0.16.0 → v0.17.0: Agent Runtime 新增，Provider 接口不变
- v0.17.0 → v0.18.0: Tool Runtime 新增，Agent Runtime 接口不变
- v0.18.0 → v0.19.0: MCP Adapter 新增，Tool Runtime 接口不变
- v0.19.0 → v0.20.0: Workflow Engine 新增，Agent/Tool 接口不变
- v0.20.0 → v0.21.0: Scheduler Runtime 新增，Workflow 接口不变
- v0.21.0 → v0.22.0: Task Runtime 新增，Scheduler/Workflow 接口不变
- post-v0.33.0 main（SP-004）: 新增 Canonical UserTask 与真实 Task API；尚未进入新的正式 Release，Reminder/Scheduler Bridge 留给 SP-005
- post-v0.33.0 main（SP-005）: 新增 Reminder/Occurrence、Scheduler CAS claim 与 Saga reconciliation；已通过 PR #10 合并，尚未进入新的正式 Release
- post-v0.33.0 main（SP-009）: 自然语言提醒闭环与站内状态已通过 PR #19 合并；尚未进入正式 Release
- post-v0.33.0 main（SP-010）: 持久化 Reminder Inbox、API/CLI 查询与只读自然语言列表已通过 PR #21 合并；尚未进入正式 Release

> SP-006 API Security Boundary: Integrated / Verified (Merged PR #12).

> SP-007 至 SP-011 均已 APPROVED / MERGED / RECONCILED / ARCHIVED 并进入 main，但尚未进入新的正式 Release。SP-012 已合并并完成对账。产品版本保持 `0.33.0`；Release Tag 与 GitHub Release 均为 none。
