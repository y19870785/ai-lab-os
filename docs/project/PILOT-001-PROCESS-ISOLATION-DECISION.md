# PILOT-001 进程隔离时间盒与备选路线决策包

> 日期：2026-08-14
> 重建来源：`c8f972e` 决策包与 `7a0e852` UID 隔离证据
> 状态：EVIDENCE_ONLY / COMPLEMENTARY_DEPLOYMENT_PROFILE / NOT_SUPERSEDING_PR_79 / NOT_PRODUCT_IMPLEMENTATION / NOT_MERGE_AUTHORIZED
> 决策门禁：Owner 在下列方案中选择一项，选择结果记录为正式决策后再启动对应任务。

## 问题陈述

- IB-IMP-A 在真实 Ubuntu 24.04.4 / WSL2 环境证明：同 UID 独立进程可执行 `pidfd_open(434)` + `pidfd_getfd(438)` 复制 gateway 持有的匿名 `socketpair()` capability，并调用 issuer 签名 oracle。
- Spike 内核缺少 `/proc/sys/kernel/yama/ptrace_scope`，SPIKE-F 判定 `LOCAL_SHELL_CANNOT_CONNECT_TO_ISSUER` 为 FAIL（duplicated=true / invoked=true）。
- 结论：`SIGNING_ORACLE_ISOLATION = FAILED_FOR_TESTED_TOPOLOGY`，`PROCESS_ISOLATION = UNRESOLVED`，Fresh Owner Ingress Evidence 为 `UNSUPPORTED`，Phase 1 未授权。
- P1A 只证明本机可信 host（无 hostile same-UID 进程）下的内部确认闭环；该结论不解决进程隔离。

## 隔离方案对比

| 方案 | 机制 | 可行性评估 | 对既有设计影响 | 部署成本 |
| --- | --- | --- | --- | --- |
| A：不同 UID 专用签名服务 | issuer 以独立用户运行，`pidfd_getfd` 需 ptrace 权限跨 UID 被拒 | WSL2 Ubuntu 24.04 支持 systemd，中等可行；需验证无 sudo 捷径 | 保持 Option D 与 RFC-033 边界 | 低 |
| B：容器或用户命名空间 | issuer 在独立 user/PID namespace 内以不同 UID 运行 | WSL2 支持，可行；需处理 WeCom 回调网络路径 | 保持 Option D；IPC 边界需重验 | 中 |
| C：远程签名服务 | 私钥与 oracle 移出 Hermes 侧，网络 IPC 带认证 | 隔离最强，但与 approved 的 anonymous capability 前提冲突 | 需重新设计，偏离 RFC-033 边界 | 高 |
| D：AppArmor 或 seccomp 禁 `pidfd_getfd` | 限制 agent 进程系统调用 | 第三方 agent 不配合时不可控；WSL2 支持有限 | 不依赖，风险高 | 低但不可靠 |
| E：备选路线——受控桌面入口 | 用户在本地受控 API 或 CLI 直接确认，不依赖 WeCom 入站隔离 | 立即可闭环信任模型，不解决企业微信自然交互 | 独立于 PILOT-001 的过渡能力 | 低 |

## 时间盒提案

- 时间盒：2026-08-14 起一周（至 2026-08-21），仅做方案 A 的受控 spike：在真实 WSL2 环境验证独立 UID 的 issuer 服务可阻止同 UID 攻击进程经 `pidfd_getfd` 复制 capability。
- 时间盒内不授权任何业务 mutation、Phase 1 或 Bridge 实现；spike 失败或超时均 fail closed。
- 时间盒结果二选一：验证通过则单独申请 IB-IMP-A 续作或 IB-IMP-B 授权；未通过则转入方案 E。

## 建议

1. 首选方案 A（不同 UID 签名服务）作为一周时间盒的验证目标，改动最小且保留 Option D 设计。
2. 并行准备方案 E（受控桌面入口）作为 fallback，使产品增量不依赖 WeCom 入站隔离。
3. 时间盒到期后无论结果，均形成正式决策；任何治理状态更新都需要独立任务与授权。

## 执行结果（2026-08-14，Owner 授权方案 A）

- 方案 A spike 已完成并通过：跨 UID `pidfd_getfd` 被内核拒绝（EPERM），同 UID 完整攻击复现（duplicated=true / invoked=true）。详见 [P1B 隔离 Spike 结果](../acceptance/PILOT-001-P1B-UID-ISOLATION-SPIKE.md)。
- 时间盒（2026-08-21）在期限内完成验证。
- 后续需独立任务与授权才能启动 IB-IMP-A 续作或 IB-IMP-B；本次 spike 不授权 Phase 1、Bridge 实现或真实业务 mutation。

## Owner 决策选项

| 选项 | 含义 | 后续动作 |
| --- | --- | --- |
| A | 授权方案 A 一周 spike | 启动隔离验证任务，需独立任务单 |
| B | 采用方案 E 备选路线 | 规划受控桌面入口闭环，WeCom 降级为规划保留 |
| C | 继续等待 | 维持现状，Pilot 保持 PHASE_1_NOT_AUTHORIZED |

## 相关文档

- [可信入站证据桥设计](PILOT-001-TRUSTED-INGRESS-EVIDENCE-BRIDGE.md)
- [IB-IMP-A 安全 Spike 验收](../acceptance/PILOT-001-IB-IMP-A-hermes-capability-spike.md)
- [RFC-033 可信入站证据桥](../rfc/033-trusted-ingress-evidence-bridge.md)
- [ADR-073 入站证据消费](../adr/ADR-073-ai-lab-owned-ingress-evidence-consumption.md)
