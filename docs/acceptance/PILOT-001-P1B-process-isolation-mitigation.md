# PILOT-001-P1B 进程隔离缓解与受支持 Pilot 部署 Profile 验收

## 1. 安全分类与授权边界

本验收只证明 **tested Pilot profile**：

```text
PILOT_GRADE_LOCAL_PROCESS_ISOLATED_PROFILE_V1
PILOT_PROCESS_ISOLATION_PROVEN_FOR_SUPPORTED_PROFILE
NOT_PRODUCTION_SECURE
NOT_ENTERPRISE_SECURE
NOT_FULLY_ISOLATED
```

必须永久保留的历史负面证据与未解决状态：

```text
SIGNING_ORACLE_ISOLATION_FAILED_FOR_TESTED_TOPOLOGY
PRODUCTION_PROCESS_ISOLATION_UNRESOLVED
PHASE_1_FULL_NOT_AUTHORIZED
PHASE_2_NOT_AUTHORIZED
REAL_BUSINESS_MUTATION_NOT_AUTHORIZED
```

本任务仅限：内部应用代码安全审计、服务器基线加固、恶意行为规则拦截、异常流量监控、
系统漏洞修复验证、红蓝防御演练防守方策略编写。所有攻击验证均在本地隔离 worktree、
WSL2 临时子进程与 synthetic issuer harness 内完成；未扫描网络、未探测外部目标、
未使用真实凭据或真实业务数据。

## 2. 环境与基线

### 2.1 执行环境（真实 WSL2）

```text
OS: Ubuntu 24.04.4 LTS / WSL2
Kernel: Linux 5.15.167.4-microsoft-standard-WSL2 x86_64
Hermes: Hermes Agent v0.20.0 (2026.8.3)
Hermes Python: 3.11.15
System Python: 3.12.3
UID: 1001
Yama: absent
ptrace_scope: unavailable
```

### 2.2 权威基线（Canonical baseline）

```text
Canonical Base: f01a8c74ab280af25b1d15453daf0a2216f05c6a
origin/main == canonical base（fetch --prune 后核对，无 BASE_DRIFT）
```

## 3. Phase A：负面基线复现（真实攻击）

修改 mitigation 前，旧 authoritative attack harness 已再次于真实 WSL2 运行：

```text
wsl.exe -d Ubuntu --cd /mnt/c/Users/hechao/Documents/AI-Lab-PILOT001-P1B -- \
  env PILOT001_RUN_REAL_CAPABILITY_ATTACK=1 \
  /home/hechao/.hermes/hermes-agent/venv/bin/python \
  -m pytest tests/spike/test_pilot_001_ingress_capability.py -q -s
.......... [100%]
10 passed in 1.37s
```

独立诊断捕获的实际 baseline attack JSON（无 hardening 对照）：

```json
{
  "fd_in_argv": false,
  "fd_in_environment": false,
  "pidfd_getfd": {
    "supported": true,
    "duplicated": true,
    "invoked": true,
    "errno": null
  },
  "proc_duplicated": false,
  "proc_errno": 6
}
```

结论：

```text
trusted holder: PASS
ordinary child inherited capability: DENIED
/proc fd duplication: DENIED
same-UID pidfd_getfd duplicated: true
attacker issuer invoked: true
BASELINE_ATTACK: REPRODUCED
```

## 4. 候选缓解：进程本地 Non-Dumpable Gateway

机制（仅 Pilot 最小实现，不修改 Hermes source、不 patch site-packages）：

```text
final Python process starts
  -> prctl(PR_SET_DUMPABLE, 0)
  -> verify prctl(PR_GET_DUMPABLE) == 0 (fail closed)
  -> only then enter gateway runtime (runpy, 无后续 exec)
```

实现文件：

- `applications/pilot_001_ingress_bridge/process_isolation.py`（新增，单一职责 Pilot-only hardening 模块）
  - Linux-only `prctl(PR_SET_DUMPABLE, 0)`；
  - `PR_GET_DUMPABLE` 运行时验证，apply/query 失败或 effective state 非 0 时抛错拒绝继续；
  - `--check` 自检模式；`--module <mod>` 在最终 Python 进程内 harden 后经
    `runpy.run_module()` 进入目标模块（无 exec 边界）。
- `applications/pilot_001_ingress_bridge/launcher.py`（最小修改）
  - `build_gateway_command()` 改为经 bootstrap 进入 `gateway.run`：最终 Hermes Python
    进程先 harden、verify 0，再进入 gateway runtime（非 parent/launcher harden 后 exec）；
  - `run_pilot_gateway()` 在 exact-four tool gate 之后、启动 gateway 之前增加
    `verify_pilot_process_isolation()` 自检，链路失败则拒绝启动（fail closed）。
- `tests/spike/pilot_001_ingress_capability/gateway_probe.py`（最小修改）
  - 仅在 `PILOT001_REQUIRE_PROCESS_ISOLATION=1` 时启用候选 hardening；
  - startup / capability acquired / post-child 三阶段记录 `PR_GET_DUMPABLE`。
- `tests/spike/test_pilot_001_process_isolation.py`（新增，P1B Linux explicit-run 测试）。

## 5. 主动攻击验收（真实 WSL2 mitigation）

命令：

```text
wsl.exe -d Ubuntu --cd /mnt/c/Users/hechao/Documents/AI-Lab-PILOT001-P1B -- \
  env PILOT001_RUN_REAL_CAPABILITY_ATTACK=1 \
  /home/hechao/.hermes/hermes-agent/venv/bin/python \
  -m pytest tests/spike/test_pilot_001_process_isolation.py -q -s
.. [100%]
2 passed in 2.40s
```

独立诊断捕获的实际 holder/attack JSON（mitigated）：

```json
{
  "holder": {
    "receipt_accepted": true,
    "child": {"fd_visible": false},
    "hardening": {
      "startup": 0,
      "capability_acquired": 0,
      "post_child": 0
    }
  },
  "attack": {
    "fd_in_environment": false,
    "fd_in_argv": false,
    "proc_duplicated": false,
    "proc_errno": 13,
    "pidfd_getfd": {
      "supported": true,
      "duplicated": false,
      "invoked": false,
      "errno": 1
    }
  }
}
```

逐项结论：

```text
A. Legitimate Capability Path (trusted plugin/gateway holder -> issuer): PASS
B. Ordinary Child Isolation (agent/tool child -> inherited capability): DENIED
C. Environment (capability/token/private material in env): NO
D. argv (capability/token/private material in argv): NO
E. Named Endpoint (connectable named socket/port): NO
F. /proc duplication (/proc/<pid>/fd/<fd>): DENIED (proc_errno=13 EACCES)
G. pidfd_getfd duplication: DENIED (errno=1 EPERM), invoked=false
```

## 6. 有效 Hardening 运行时证明

从真实 holder process 证明：

```text
PR_GET_DUMPABLE (startup): 0
PR_GET_DUMPABLE (capability_acquired): 0
PR_GET_DUMPABLE (post_child): 0
```

gateway startup 后、capability 进入 holder 后、tool child 生成后状态均保持 0；
任何代码路径重新变为 dumpable=1 都会触发 `PILOT_PROCESS_ISOLATION_INEFFECTIVE` 并拒绝继续。

## 7. 失败即关闭（Fail-Closed）启动顺序

```text
final Python process harden
  -> runtime verify 0
  -> capability holder/runtime 进入
  -> tool namespace resolution（Hermes exact four）
  -> exact-four gate（enforce_model_tool_profile）
  -> 再次 verify 0（verify_pilot_process_isolation --check）
  -> 正式接收 WeCom traffic 前 gate 完成
```

如果 hardening 无法应用（非 Linux、prctl 失败、effective != 0），Gateway/trusted Pilot path
拒绝启动。Windows 非 real 快速检查结果：`10 passed, 2 skipped in 0.07s`（skip 为 P1B
explicit Linux-only attack 测试在非 real 下正确跳过；这不构成安全 PASS，安全结论以
WSL2 真实运行为准）。

## 8. 重启与重放安全（Restart / Replay）

连续两次启动验证 hardening re-apply 与 restart denial：

```json
RUN 1: hardening {startup:0, capability_acquired:0, post_child:0},
       pidfd_getfd {duplicated:false, invoked:false, errno:1}
RUN 2: hardening {startup:0, capability_acquired:0, post_child:0},
       pidfd_getfd {duplicated:false, invoked:false, errno:1}
```

结论：RESTART_SECURITY: PASS。第二次启动重新 harden，旧 capability 不复用，攻击仍失败。

## 9. Hermes / P1A 回归验证

Hermes actual model namespace 保持精确：

```text
mcp__ai_lab_p1a__ai_lab_interaction_preview
mcp__ai_lab_p1a__ai_lab_interaction_status
mcp__ai_lab_p1a__ai_lab_interaction_view
mcp__ai_lab_p1a__ai_lab_interaction_confirm
```

EXACT FOUR TOOLS：PASS（`tests/applications/pilot_001_ingress_bridge` 19 passed；
未出现 terminal/shell/python/process/browser/computer/execute/verify/recover/approve/
tool_search/通用 arbitrary tool）。

## 10. 部署 Profile 定义

```text
Profile ID: PILOT_GRADE_LOCAL_PROCESS_ISOLATED_PROFILE_V1
```

- supported OS family：Linux（POSIX）；
- tested OS：Ubuntu 24.04.4 LTS（WSL2）；
- tested kernel：5.15.167.4-microsoft-standard-WSL2 x86_64；
- tested Hermes version：v0.20.0（2026.8.3）；
- required UID assumptions：single-user / same-UID topology（UID 1001）；
- required process topology：issuer 与 gateway 为独立匿名 endpoint 连接的本地进程，
  capability FD 固定为 198，不经 argv/env/named endpoint 传递；
- required hardening mechanism：final Python process 内 `prctl(PR_SET_DUMPABLE, 0)`；
- required startup sequence：final process harden -> verify 0 -> runtime；
- required runtime assertion：startup / capability acquired / post-child 三阶段
  `PR_GET_DUMPABLE == 0`；
- attacker model：同 UID 独立本地进程，可 `pidfd_open` gateway pid，可尝试
  `pidfd_getfd` 复制 capability FD 并调用 issuer（signing oracle）；
- explicitly excluded attacker capabilities：root、不同 UID、seccomp/LSM 绕过、
  kernel 漏洞、debugger 直连（Yama absent 的环境未依赖 ptrace_scope）；
- restart behavior：新进程重新 harden，旧 capability 不复用，攻击仍失败；
- fail-closed behavior：hardening 无法应用或 effective != 0 时拒绝启动；
- rollback / disable procedure：不设置 `PILOT001_REQUIRE_PROCESS_ISOLATION` 即回到
  未 hardening 的 harness 行为（用于对照/回滚；生产 Pilot 必须启用并保持 fail closed）。

本 profile 仅证明 **tested Pilot profile**，不得写成 production secure、enterprise secure、
fully isolated 或 general process isolation resolved。

## 11. 验证矩阵（本任务执行记录）

| 项 | 命令/范围 | 结果 |
|---|---|---|
| A. IB-IMP-A 旧攻击套件 | WSL2 `test_pilot_001_ingress_capability.py`（real） | 10 passed（负面 baseline 仍复现） |
| B. P1B mitigation 攻击 | WSL2 `test_pilot_001_process_isolation.py`（real） | 2 passed（含 restart） |
| C. P1A relevant | `tests/applications/pilot_001_ingress_bridge` | 19 passed |
| C. P1A acceptance | `test_acc_021_canonical_trusted_interaction.py` | 7 passed |
| D. governance | `tests/governance` | 37 passed |
| E. default non-real pytest | `tests -q --tb=no` | 1867 passed, 2 skipped |
| F. explicit non-real pytest | `tests --ignore=tests/real -m "not real"` | 1867 passed, 2 skipped |
| G. changed-files Ruff | 变更 Python 文件 | All checks passed |
| H. git diff --check | 工作区 | 无空白错误（仅 LF/CRLF 警告） |

## 12. 机器治理标记（Marker）

新增（P1B PASS）：

```text
PILOT_001_P1B_PROCESS_ISOLATION_MITIGATION_PROVEN
PILOT_GRADE_LOCAL_PROCESS_ISOLATED_PROFILE_V1
PILOT_PROCESS_ISOLATION_PROVEN_FOR_SUPPORTED_PROFILE
```

必须保留（历史负面证据与未解决状态）：

```text
SIGNING_ORACLE_ISOLATION_FAILED_FOR_TESTED_TOPOLOGY
PRODUCTION_PROCESS_ISOLATION_UNRESOLVED
PHASE_1_FULL_NOT_AUTHORIZED
PHASE_2_NOT_AUTHORIZED
REAL_BUSINESS_MUTATION_NOT_AUTHORIZED
```

## 13. 风险说明、使用前提与授权边界

- 风险说明：本缓解依赖 Linux dumpable 语义与同 UID 进程模型；root / 不同 UID / 内核级
  攻击者不在本 profile 威胁模型内；Yama 缺失的环境未提供 ptrace_scope 纵深防御。
- 使用前提：仅限上述 tested Pilot profile；必须启用 `PILOT001_REQUIRE_PROCESS_ISOLATION`
  并保持 fail-closed 启动；禁止用于生产/企业/通用安全声明。
- 授权边界：本任务仅授权 PILOT-001-P1B 范围的安全修复验证、最小 Pilot-only 实现、
  证据与治理文档、提交、推送与 Draft PR。Ready、Merge、Tag、Release、REL-036、
  Phase 2、真实 UserTask mutation、真实 AI-Lab provider、Hermes core 修改、
  site-packages patch、sudo、sysctl 写入、/etc 或全局 systemd 修改、永久 host 安全策略
  变更均未授权。
- 本验收证明 tested Pilot profile 的进程本地隔离；通用 process isolation 未解决。

## 14. 停止条件与独立审查状态

遇到的停止条件：无（canonical base 无漂移；baseline attack 正常复现；candidate
mitigation active attack 真实 DENIED；restart PASS；exact four tools 无回归；
无 UserTask mutation；AI-Lab real Provider 为 0；无 Hermes core 修改；无 sudo/全局
host 修改；无 credential 暴露）。

最终治理状态：

```text
PILOT-001-P1B: IMPLEMENTED / EVIDENCE_COMPLETE / PENDING_INDEPENDENT_REVIEW
```

PR 保持 OPEN / DRAFT；不转 Ready、不 Merge。