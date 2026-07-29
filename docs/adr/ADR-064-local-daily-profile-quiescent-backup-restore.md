# ADR-064：本地日常运行配置与静止备份/恢复合同

- Status: Accepted
- Date: 2026-07-29
- SP: SP-020

## 背景（Context）

当前 settings 默认以 working directory 推导 `.env` 与 `data/`。同一 checkout 从不同
目录启动时，可能静默打开不同 SQLite 数据。AI-Lab 又跨多个 SQLite 文件持久化
UserTask、Reminder、Scheduler、Inbox、Waiting-For、Work Log 与 Memory；运行中逐个
复制文件不能默认构成一致快照。

## 决策（Decision）

SP-020 的 Windows Local Daily Profile 必须显式固定：

- 绝对 `AI_LAB_DATA_DIR`；
- 归属于该 data root 的绝对 `AI_LAB_SQLITE_DIR`；
- 显式 IANA timezone 与 Provider mode；
- UserTask、Daily Review、Reminder、Scheduler 开启；
- Knowledge、Coordination 关闭；
- API 开启、auth 明确开启、非空 token；
- API 只绑定 `127.0.0.1`；
- 启动后执行 health/readiness，停止时执行受控优雅关闭；
- 配置诊断只显示非敏感有效值，不回显 secret。

Profile 不得依赖调用者的 working directory 决定业务数据位置。配置缺失或无效必须明确
失败，不得自动切换 data directory、mock Provider 或关闭 auth。

备份合同采用 Quiescent Backup，而不是在线跨库快照：

```text
停止接受新工作
→ 优雅关闭 SystemContainer
→ 确认数据库连接关闭
→ 复制完整 data directory
→ 恢复到不同隔离目录
→ 用新进程和新 SystemContainer 启动
→ 验证 canonical 对象、Daily Review、Scheduler、Reminder、Inbox Saga 与 Waiting-For
```

完整复制包括 SQLite 数据库以及可能存在的 `-wal`、`-shm` 和可选 Chroma 目录；不得
只挑选部分 `.db`。恢复验证不得覆盖原数据目录。

## 结果（Consequences）

- 日常进程与恢复进程对数据位置有可复现证据。
- 备份前需要停机窗口，但不需要跨库事务或 schema migration。
- STOPPED/FAILED container 不复用；恢复必须创建新 container。
- `DatabaseManager.backup()` / `restore()` 当前未实现，不把它们当成已交付工具。
- 若未来必须在线备份，需要新的独立设计与授权。

## 停止条件

出现以下任一情况停止 SP-020 当前实现阶段：

- 数据目录变更会静默遗弃既有数据；
- shutdown 不能证明连接已关闭或 Scheduler 幂等；
- restart 出现重复 job、丢失 job、Reminder/Saga 状态漂移；
- 恢复需要在线跨多个 SQLite 的一致快照、跨库事务或 migration；
- Windows 环境无法稳定启动、停止或隔离恢复。

## 验证要求

ACC-020 必须使用真实 Windows subprocess、真实 SQLite 与两个不同绝对 data roots：

1. 启动 Local Daily Profile 并通过 health/readiness；
2. 创建覆盖所有启用 canonical source 的数据；
3. 优雅关闭并验证连接释放；
4. 复制完整 source data root 到 isolated restore root；
5. 使用新 SystemContainer 从 restore root 启动；
6. 核对对象、revision、scheduler jobs/runs、Reminder reconciliation、Inbox claim/Saga、
   Waiting-For history 与 today/yesterday Review；
7. Provider call 为 0，原 data root 不被修改。

## 治理

本 ADR 已随独立审查通过并合并的 SP-020 Planning Baseline Accepted，但不批准
Local Daily Profile、备份工具、schema、migration、version、Tag 或 Release 变更。
