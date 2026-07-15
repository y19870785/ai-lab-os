# 版本兼容性矩阵

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

> SP-006 API Security Boundary: Integrated / Verified (Merged PR #12, not merged).
