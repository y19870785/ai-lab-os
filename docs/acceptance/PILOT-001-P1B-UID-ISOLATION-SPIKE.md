# PILOT-001 P1B 不同 UID 签名服务隔离 Spike 结果

> 日期：2026-08-14
> 任务来源：[PILOT-001 进程隔离决策包](../project/PILOT-001-PROCESS-ISOLATION-DECISION.md) 方案 A
> 状态：EVIDENCE_ONLY / COMPLEMENTARY_DEPLOYMENT_PROFILE / NOT_SUPERSEDING_PR_79 / NOT_PRODUCT_IMPLEMENTATION / NOT_MERGE_AUTHORIZED
> 结论：不同 UID 签名服务可阻断同 UID 攻击进程经 `pidfd_getfd` 复制并调用 issuer capability；方案 A 在已测拓扑下验证通过，不构成生产安全结论。

## 目标

在真实 Ubuntu/WSL2 环境验证决策包方案 A：issuer 签名服务以独立 UID 运行时，`pidfd_getfd` 跨 UID 复制被内核拒绝。

## 环境

- WSL2 / Ubuntu 24.04（真实 Pilot 同拓扑）
- kernel 支持 `pidfd_open(434)` 与 `pidfd_getfd(438)`
- yama `ptrace_scope`：absent（保护依赖内核 UID 级 `ptrace_may_access` 检查）
- 攻击进程以非 root UID 运行，无 `CAP_SYS_PTRACE`

## 方法

- 受保护进程（holder）持有 anonymous socketpair 客户端端并映射为 FD 198，模拟签名服务 capability，以目标 UID 运行。
- 响应线程持有服务端并对调用返回 receipt，证明复制后的 FD 是活的 capability。
- 攻击进程对 holder PID 执行 `pidfd_open` + `pidfd_getfd`，尝试复制并调用。

## 结果

| 阶段 | 受保护进程 UID | 攻击者 UID | 结果 |
| --- | --- | --- | --- |
| Phase 1 基线 | 1001（hechao） | 1001 | duplicated=true / invoked=true（完整攻击复现，同 IB-IMP-A） |
| Phase 2 隔离 | 1002（ailab-issuer） | 1001 | duplicated=false / `pidfd_getfd_errno=1`（EPERM） |

verdict：same_uid_pidfd_getfd_duplicated=true，same_uid_invoked=true，different_uid_pidfd_getfd_duplicated=false，isolation_holds=true。

## 结论

- 同 UID：`pidfd_getfd` 可复制并调用 capability（复现 IB-IMP-A `FAILED_FOR_TESTED_TOPOLOGY`）。
- 跨 UID：`pidfd_getfd` 被内核拒绝（EPERM），攻击在窃取步骤即被阻断。
- 方案 A 在真实 WSL2 拓扑下验证通过，满足决策包一周时间盒要求。

## 边界与后续

- 攻击进程必须无 `CAP_SYS_PTRACE`、无 sudo 提权路径；WSL2 默认用户有免密 sudo，部署时须确保 agent 运行用户无提权能力。
- 本 spike 不构成生产安全结论，不授权 Phase 1、Bridge 实现或真实业务 mutation。
- spike 会创建系统用户 `ailab-issuer`；为可复现保留，不涉及 Git 或产品代码。
- 相关代码位于 [tests/spike/pilot_001_uid_isolation](../../tests/spike/pilot_001_uid_isolation/)，仅 SPIKE 使用。
