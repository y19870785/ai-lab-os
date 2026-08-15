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
- `tests/applications/pilot_001_ingress_bridge/test_p1b_r1_actual_runtime.py`（新增，P1B-R1 实际运行时证据测试）
  与 `tests/applications/pilot_001_ingress_bridge/stub_gateway_runtime.py`（新增，Pilot-only stub gateway）。

## 4A. P1B-R1：实际运行时证据闭环（Actual Runtime Evidence Closure）

### 证据类型区分（R1 审查要求）

本验收明确区分两类证据，任何一处都不得混用：

| 类别 | 来源 | 直接观察（observation） | 推断（inference） |
|---|---|---|---|
| CONTROLLED VALIDATION HOLDER | `gateway_probe.py`（spike fixture） | 三阶段 `PR_GET_DUMPABLE=0` | 该 holder 是 repository-controlled fixture，不是实际 Hermes gateway runtime |
| ACTUAL HERMES GATEWAY RUNTIME | `run_pilot_gateway()` 实际启动链路 | evidence 文件 pid + 内核拒绝跨进程 mem 访问 | 同一进程进入 `gateway.run` 且保持隔离（基于 PID 匹配的 process identity linkage） |

`gateway_probe.py` 的三阶段结果只作为受控防御性回归 fixture，不再被描述为
actual Hermes holder 三阶段 runtime proof；actual runtime 证明来自 launcher 实际链路。

### 进程身份关联（Process Identity Linkage）

launcher 启动实际 gateway 前把 `PILOT001_RUNTIME_EVIDENCE_FILE` 指向临时 project 内的
evidence 文件；bootstrap（`process_isolation.py` 的 `run_hardened_module`）在应用隔离后先写
`stage=dispatching`，它仅表示调用前准备状态，不构成完成证据。`runpy.run_module()` 开始后，
目标模块 resolved source file 的首个实际执行 frame 写入 `stage=module_started`。JSON 包含
`pid`（最终进程）、`dumpable`（0）、`pr_get_dumpable`（0）、`stage`、`module` 与 `filename`；受控模块正常返回后才写
`stage=returned`。

launcher（`run_actual_gateway()`）验证三件事：

```text
1. evidence.pid == subprocess.Popen(...).pid   同一 process identity
2. evidence.dumpable == 0                      隔离已在最终进程内应用
3. observe_kernel_dumpable(pid) == 0           内核拒绝跨进程 /proc/<pid>/mem 访问
```

其中 `observe_kernel_dumpable()` 不从 bootstrap 读打印，而是从 launcher（不同进程）尝试
`open("/proc/<pid>/mem")`：目标 non-dumpable 时内核返回 EACCES/EPERM（观察返回 0）；
dumpable=1 时 open 成功（观察抛 `KERNEL_MEM_ACCESSIBLE`）。这是内核强制语义的直接观察。

### 实际链路证据（WSL2 explicit run）

```text
wsl.exe -d Ubuntu --cd /mnt/c/Users/hechao/Documents/AI-Lab-PILOT001-P1B -- \
  env PILOT001_RUN_REAL_CAPABILITY_ATTACK=1 \
  /home/hechao/.hermes/hermes-agent/venv/bin/python \
  -m pytest tests/applications/pilot_001_ingress_bridge/test_p1b_r1_actual_runtime.py -q -s
...
PILOT_ACTUAL_RUNTIME_EVIDENCE pid=<pid> module=<stub> stage=module_started filename=<stub.py> dumpable=0 kernel_dumpable=0 proc_status=<pid>
5 passed
```

`test_p1b_r1_actual_gateway_link_on_wsl2` 用 `run_actual_gateway()`（launcher 实际 gateway 启动
路径）启动 stub gateway：bootstrap 在最终 Python 进程内 harden、写 evidence、经 runpy 进入 stub
（同一进程，无 exec）；launcher 校验 evidence.pid == Popen pid、dumpable=0、内核拒绝跨进程 mem
访问，并在 gateway runtime 返回后确认 evidence `stage=returned` 仍记录同一 pid——证明
应用隔离的进程 == 运行 gateway runtime 的进程 == runtime 结束后仍存活的进程。

Windows 非 real 下该测试正确 skip（`os.name != posix` 或未设置 `PILOT001_RUN_REAL_CAPABILITY_ATTACK`）；
Windows 上另有 3 个单测覆盖 launcher wiring 契约（bootstrap→module 命令、evidence 等待的 PID 匹配语义）。

### `verify_pilot_process_isolation(--check)` 的定位

`--check` 自检保留为 prerequisite/self-test：它证明 bootstrap 机制可在目标环境应用。
它**不等于**实际 gateway process runtime proof；actual runtime proof 由上述
`run_actual_gateway()` 链路（evidence PID + 内核 mem 观察）提供。

## 4B. P1B-R2：证据精度闭环（Evidence Precision Closure）

R2 关闭 R1 审查指出的四个精确证据问题：

### A. Stub Runtime 与 Actual Hermes Runtime 严格区分

R1 的 `test_p1b_r1_actual_gateway_link_on_wsl2` 实际进入的是 repository-controlled
stub 模块（`stub_gateway_runtime.py`），只能证明 bootstrap wiring / PID linkage /
evidence 机制 / runpy 进程身份保持 / 内核观察机制可用。R2 将其重新分类为：

```text
CONTROLLED_RUNTIME_LINK_VALIDATION
```

该测试不再以任何名称暗示 actual Hermes runtime。actual Hermes 证明由新增的
`test_p1b_r2_actual_hermes_gateway_run_runtime_entry_on_wsl2` 提供。

### B. Actual Hermes `gateway.run` Runtime-Entry 证明

使用真实 Hermes Python（`/home/hechao/.hermes/hermes-agent/venv/bin/python`）与默认
`gateway_module="gateway.run"`（不传 stub），经现有临时 Pilot project / launcher 链路
实际启动 Hermes gateway，并在其目标文件内部首个 frame 产生 `stage=module_started` 后由 runner
受控结束（`runtime_entry_only=True`）。WSL2 explicit 实测：

```text
PILOT_ACTUAL_RUNTIME_EVIDENCE pid=2327561 module=gateway.run stage=module_started filename=/home/hechao/.hermes/hermes-agent/gateway/run.py PR_GET_DUMPABLE=0 dumpable=0 kernel_dumpable=0 proc_status=2327561
12 passed（R2 文件）；R1 + R2 explicit suite 共 17 passed
```

直接观察项：

```text
spawned executable == 实际 Hermes Python        ✓
requested module == gateway.run                 ✓
evidence.module == gateway.run                  ✓
evidence.pid == spawned Popen.pid               ✓
evidence.dumpable == 0                          ✓
evidence.pr_get_dumpable == 0                   ✓
evidence.stage == module_started                ✓
evidence.filename == actual Hermes gateway/run.py ✓
kernel mem observation == 预期拒绝（EACCES）     ✓
gateway 进程在 evidence 建立后仍存活            ✓
```

本证明为 **RUNTIME_ENTRY_PROVEN**，不等同于 FULL_GATEWAY_SERVICE_LIFECYCLE_PROVEN：
不要求 Hermes gateway 完成完整业务生命周期，不发送真实 WeCom 业务消息，不产生
UserTask / Execution / AI-Lab real provider 调用。目标模块导入失败、在 checkpoint 前退出，
或在 checkpoint 后稳定存活观察窗口内提前退出，均 fail closed。

### C. Kernel Observation 严格 errno 检查

`observe_kernel_dumpable()` 现在只把明确属于预期访问拒绝的 errno 判为 PASS：

```text
EACCES / EPERM  ->  KERNEL_ACCESS_DENIED_AS_EXPECTED（返回 0）
其他 OSError    ->  FAIL CLOSED（PILOT_ACTUAL_RUNTIME_KERNEL_OBSERVATION_UNEXPECTED）
open 成功        ->  FAIL（PILOT_ACTUAL_RUNTIME_KERNEL_MEM_ACCESSIBLE）
```

进程不存在、路径不存在、I/O failure、unexpected proc state、permission observation
unsupported 均 fail closed，不得解释为 isolation PASS。单测覆盖 EACCES/EPERM 通过、
ENOENT/EIO/ENOTDIR fail-closed、成功 open fail-closed。

### D. Launcher 自身验证 Final Runtime Evidence

正式 `run_actual_gateway()` 现在由 launcher 自身强制验证全部 runtime-entry 字段：

```text
evidence.pid == Popen.pid                     PID 匹配（不匹配即 fail）
evidence.module == gateway_module             module 匹配（stub 不能冒充 gateway.run）
evidence.dumpable == 0                        isolation 已应用
evidence.pr_get_dumpable == 0                 PR_GET_DUMPABLE checkpoint 已验证
evidence.stage == module_started              目标文件内部 frame（dispatching 不通过）
evidence.filename == resolved target file     路径匹配；gateway.run 必须属于 Hermes 安装
gateway.poll() is None                        稳定窗口后仍存活（提前退出即 fail）
observe_kernel_dumpable(pid) == 0             内核预期拒绝
```

`stage=returned` 只属于 CONTROLLED_RUNTIME_COMPLETION_PROOF（stub 测试验证同一进程
贯穿 runtime 并返回）；它**不是** actual Hermes service startup 的必要条件。
生产 Pilot gateway 正常不返回，因此 launcher 不要求 `stage=returned`。

### Evidence Schema 加强

runtime evidence 至少包含 `pid` / `dumpable` / `pr_get_dumpable` / `stage` / `module` / `filename` 六字段；launcher 对
actual Hermes path 全部检查，不只检查 PID。wrong module、只有 dispatching、目标模块无法解析或
导入、提前退出、超时、错误 PID 与 filename 路径冒充均 fail closed。evidence 不含 secret、capability content、
FD content、token 或 business payload。

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

分两层证明（R1 起明确区分）：

### 6.1 CONTROLLED VALIDATION HOLDER（受控 fixture）

`gateway_probe.py` 三阶段（repository-controlled，不是实际 Hermes runtime）：

```text
PR_GET_DUMPABLE (startup): 0
PR_GET_DUMPABLE (capability_acquired): 0
PR_GET_DUMPABLE (post_child): 0
```

### 6.2 ACTUAL HERMES GATEWAY RUNTIME（实际 launcher 链路）

从 `run_actual_gateway()` 实际启动的最终 Python 进程证明：

```text
evidence.pid == Popen.pid            process identity linkage（同一进程）
evidence.dumpable == 0               isolation 已应用（bootstrap 内 PR_GET_DUMPABLE）
observe_kernel_dumpable(pid) == 0    内核拒绝跨进程 /proc/<pid>/mem 访问（直接观察）
stage=returned 仍记录同一 pid        同一进程贯穿整个 gateway runtime
```

任何代码路径重新变为 dumpable=1 都会触发 fail-closed 拒绝继续；launcher 若发现
evidence PID 不匹配、dumpable != 0 或内核 mem 可访问，即抛错停止（不进入 supported runtime）。

## 7. 失败即关闭（Fail-Closed）启动顺序

```text
final Python process harden
  -> runtime verify 0
  -> capability holder/runtime 进入
  -> tool namespace resolution（Hermes exact four）
  -> exact-four gate（enforce_model_tool_profile）
  -> prerequisite self-test（verify_pilot_process_isolation --check）
  -> run_actual_gateway：evidence PID 匹配 + dumpable=0 + 内核 mem 拒绝
  -> 正式接收 WeCom traffic 前 gate 完成
```

`--check` 是 prerequisite/self-test（证明机制可应用），不等于 gateway runtime proof；
actual runtime proof 由 `run_actual_gateway()` 的 evidence PID + 内核观察提供。
如果 hardening 无法应用（非 Linux、prctl 失败、effective != 0）或实际链路证据不满足
（PID 不匹配 / dumpable != 0 / 内核 mem 可访问），Gateway/trusted Pilot path 拒绝启动。
Windows 非 real 检查：P1B-R1 新增 3 个单测 + 既有 spike 快速检查通过（explicit Linux-only
测试在非 real 下正确 skip；这不构成安全 PASS，安全结论以 WSL2 真实运行为准）。

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
| B1. P1B-R1 controlled stub link | WSL2 `test_p1b_r1_actual_runtime.py`（real explicit） | 5 passed（CONTROLLED_RUNTIME_LINK_VALIDATION） |
| B2. P1B-R2/R6 actual Hermes runtime-entry | WSL2 `test_p1b_r2_actual_hermes_runtime.py`（real explicit） | 12 passed（module_started + filename + fail-closed negatives） |
| C. P1A relevant | `tests/applications/pilot_001_ingress_bridge` | 23 passed, 8 skipped |
| C. P1A acceptance | `test_acc_021_canonical_trusted_interaction.py` | 7 passed |
| D. governance | `tests/governance` | 37 passed |
| E. default non-real pytest | `tests -q --tb=no` | 1871 passed, 10 skipped |
| F. explicit non-real pytest | `tests --ignore=tests/real -m "not real"` | 1871 passed, 10 skipped |
| G. changed-files Ruff | 变更 Python 文件 | All checks passed |
| H. git diff --check | 工作区 | 无空白错误（仅 LF/CRLF 警告） |

## 12. 机器治理标记（Marker）

新增（P1B PASS）：

```text
PILOT_001_P1B_PROCESS_ISOLATION_MITIGATION_PROVEN
PILOT_GRADE_LOCAL_PROCESS_ISOLATED_PROFILE_V1
PILOT_PROCESS_ISOLATION_PROVEN_FOR_SUPPORTED_PROFILE
```

R2 后新增（actual Hermes runtime-entry 证据成立）：

```text
PILOT_001_P1B_ACTUAL_HERMES_RUNTIME_ENTRY_PROVEN
```

必须保留（历史负面证据与未解决状态）：

```text
SIGNING_ORACLE_ISOLATION_FAILED_FOR_TESTED_TOPOLOGY
PRODUCTION_PROCESS_ISOLATION_UNRESOLVED
PHASE_1_FULL_NOT_AUTHORIZED
PHASE_2_NOT_AUTHORIZED
REAL_BUSINESS_MUTATION_NOT_AUTHORIZED
```

不得升级为 PRODUCTION_SECURE / ENTERPRISE_SECURE / FULLY_ISOLATED /
GENERAL_PROCESS_ISOLATION_RESOLVED。

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

P1B-R1 的 `ACTUAL_RUNTIME_EVIDENCE_COMPLETE` 表述已被 R2 修正：R1 实际进入的是 stub
模块，只能证明 controlled runtime link（CONTROLLED_RUNTIME_LINK_VALIDATION），不能证明
actual Hermes runtime。R2 使用真实 Hermes Python + `gateway.run` 建立 actual Hermes
runtime-entry 路径；R6 进一步把 pre-call `entering` 修正为非完成性的 `dispatching`，并以
实际 Hermes `gateway/run.py` 文件内首个执行 frame 产生的 `module_started` 作为完成证据
（RUNTIME_ENTRY_PROVEN）。kernel errno 仍仅 EACCES/EPERM 为预期拒绝，launcher 自身验证
pid/module/dumpable/stage/resolved filename/稳定存活；全部负向条件 fail closed。

R6 遇到的停止条件：无。actual Hermes `gateway.run` 在现有授权范围内可执行到
`module_started` evidence；未修改 Hermes core/site-packages、未使用 sudo、未改系统策略、
未扩大安全测试能力、未发送真实业务消息。

P1B / P1B-R1 / P1B-R2 均无 UserTask mutation、Execution、AI-Lab real Provider 调用、真实业务消息。

最终治理状态：

```text
PILOT-001-P1B: IMPLEMENTED / EVIDENCE_COMPLETE / PENDING_INDEPENDENT_REVIEW
PILOT-001-P1B-R2: IMPLEMENTED / ACTUAL_HERMES_RUNTIME_ENTRY_EVIDENCE_COMPLETE / PENDING_INDEPENDENT_REVIEW
```

PR 保持 OPEN / DRAFT；不转 Ready、不 Merge、不 Tag、不 Release。
最终安全结论等待 ChatGPT 对 PR #79 的下一轮独立审查。
