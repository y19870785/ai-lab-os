# PILOT-001 IB-IMP-A — Hermes 模型前 Capability 边界安全 Spike 证据

- 任务：`PILOT-001-IB-IMP-A`
- Base：`2e099aaf56b2160473e4db54397ec3864f9433ae`
- 性质：`SECURITY / COMPATIBILITY SPIKE / LIMITED IMPLEMENTATION`
- 结果：`STOPPED_SIGNING_ORACLE_ISOLATION_FAILED / CURRENT_PILOT_DEPLOYMENT_UNSUPPORTED`
- 最终独立安全审查：`PASSED`（Approved Evidence Head `a50fc8719158c07a4eee716c3513e9698c8571ff`）
- 负面证据基线：`APPROVED`
- 业务 mutation：`0`
- Real Provider：`0`

## 最终结论

当前真实 Pilot 部署不支持 RFC-033 / ADR-073 要求的同 OS 用户 signing-oracle isolation。该结论限定于已测试的
Ubuntu/WSL2、same-UID 与当前 process-hardening topology，不表示 Option D 永久不可行、Linux 同 UID isolation
普遍不可行或 RFC-033 / ADR-073 无效。RFC-033 保持 Adopted，ADR-073 保持 Accepted；Option D 设计基线保留，
process isolation unresolved，完整实现未授权。虽然受信 supervisor
可以用 `socketpair()` 建立单一、预连接、无名字、无 bearer 的 capability，且 gateway/plugin 在接管后设置
close-on-exec，使普通 Agent/tool child 不继承该 FD；但 Ubuntu 24.04.4 WSL2 当前 kernel 没有 Yama LSM，独立启动的
同 UID 进程可执行 `pidfd_open(gateway_pid)` + `pidfd_getfd(pidfd, capability_fd, 0)`，复制 gateway 持有的 endpoint，
并用伪造 `channel_event_id` frame 获得 issuer stub 的有效 test receipt。

这不是“攻击者知道 FD 编号”的保密问题：攻击者具有可调用 issuer authority。它命中任务书 Stop Condition：

```text
same-user untrusted process can invoke issuer
SIGNING_ORACLE_ISOLATION_FAILED
STOPPED_SIGNING_ORACLE_ISOLATION_FAILED
```

因此没有继续真实 Owner DM callback，没有发送真实 Message B，没有实现完整 Bridge。`body.msgid` 在实际安装的
bundled WeCom `_on_message()` 源码中位于 Agent dispatch 前，但 SPIKE-B 所要求的真实 callback 运行证据未完成，
保持 `CHANNEL_EVENT_ID_CONTRACT_UNPROVEN`。

## 真实环境

| 项目 | 实际值 |
|---|---|
| Hermes | `Hermes Agent v0.20.0 (2026.8.3)` |
| Hermes Python | `3.11.15` |
| OS | `Ubuntu 24.04.4 LTS / WSL2` |
| Kernel | `Linux 5.15.167.4-microsoft-standard-WSL2 x86_64` |
| 系统 Python | `3.12.3` |
| Gateway launch | user systemd `hermes-gateway.service` |
| Gateway ExecStart | `<HERMES_INSTALL>/venv/bin/python -m hermes_cli.main gateway run` |
| Hermes 安装方式 | editable package `hermes-agent 0.20.0` |
| Plugin discovery | bundled `<HERMES_INSTALL>/plugins/`; user `$HERMES_HOME/plugins/`; opt-in project `./.hermes/plugins/` |
| 实际 bundled WeCom path | `<HERMES_INSTALL>/plugins/platforms/wecom/adapter.py` |
| Spike plugin 惰性 fixture | `tests/spike/pilot_001_ingress_capability/fixtures/hermes_project_plugin/platforms/wecom/` |
| Gateway topology | systemd user manager → Hermes gateway → MCP watchdog → mock AI-Lab MCP |
| Provider | mock / disabled credentials |

路径使用逻辑占位符，未记录 home path、credential、raw Owner ID、raw message content 或 raw event ID。

## Plugin 与 callback 边界

Hermes v0.20.0 的 `kind: platform` user/project plugin 是正式 loader 路径；`PlatformRegistry.register()` 明确采用
last-writer-wins。项目 plugin dry-run 在未修改 Hermes core、未修改 site-packages、未持久化更改现有 Hermes config 的
条件下加载成功。R1 已从 live `./.hermes/plugins/platforms/wecom/` 删除失败 prototype；loader regression 只在临时
目录中把惰性 fixture 显式投影为 `.hermes/plugins/platforms/wecom/`，随后调用真实 Hermes `PluginManager` 扫描和加载：

```text
enabled=True
error=None
source=project
adapter_factory_module=hermes_plugins.platforms__wecom.adapter
```

bundled WeCom WebSocket adapter 的真实入站顺序为：

```text
authenticated callback payload
→ body = payload["body"]
→ body.msgid
→ Owner DM/group policy
→ MessageEvent(...)
→ handle_message(event)
→ Agent/LLM
```

bundled adapter 会把缺失 `body.msgid` 回退到 `headers.req_id` / UUID；Spike plugin 在调用 bundled `_on_message()` 前
只接受非空 `body.msgid`，不含 fallback。但由于 signing-oracle isolation 先失败，本轮没有用真实 Owner DM 执行该
callback，不能把源码可见性提升为真实运行证明。

## Capability 与 supervisor

受信 supervisor 创建一个 POSIX `socketpair()`，分别只交给 plugin/gateway 与 issuer stub。没有 named socket、port、
filesystem path、bearer token、environment secret 或 tool registry entry。受信 bootstrap 在 exec Hermes/issuer 前把唯一
继承 socket 映射为固定 FD，进程接管后立即设置 non-inheritable。supervisor 关闭自己的两个 endpoint。

| endpoint 持有方 | 初始继承 | 接管后可继承给普通 child |
|---|---:|---:|
| supervisor | 创建两端，spawn 后关闭 | 不适用 |
| gateway/plugin | 仅 plugin endpoint | 否（close-on-exec） |
| issuer stub | 仅 issuer endpoint | 否（close-on-exec） |
| Agent/tool child | 无 | 否 |
| 独立同 UID 进程 | 无正常继承 | **可用 `pidfd_getfd` 复制 gateway endpoint** |

issuer stub 只返回 domain-separated SHA-256 test receipt；没有 Ed25519、JCS、production key、issuance journal、
AI-Lab receiver 或 persistence。它的用途仅是证明复制的 endpoint 确实能调用 authority。

## 主动攻击证据

权威命令：

```text
PILOT001_RUN_REAL_CAPABILITY_ATTACK=1 \
<HERMES_PYTHON> -m pytest tests/spike/test_pilot_001_ingress_capability.py -q
```

Previous Security Evidence Head 实际：`9 passed`。R1 quarantine 后的真实 Hermes loader + active attack suite：
`10 passed`。测试把“攻击成功”作为预期负面事实锁定，避免未来把 exploit 消失或复现失败误报成证据。

| 攻击面 | 预期安全属性 | 实际 |
|---|---|---|
| Agent/tool child | FD 不继承 | PASS：child `fd_visible=false` |
| environment | 不出现 FD/token/secret | PASS |
| argv | 不出现 FD/token/secret | PASS |
| filesystem/named socket | 无可连接 endpoint | PASS |
| `/proc/<pid>/fd/<fd>` open | 不能复制 | DENIED |
| same UID `pidfd_getfd` | 不能复制/调用 | **FAIL：duplicated=true / invoked=true** |
| arbitrary frame | issuer 不接受 | **FAIL：复制 endpoint 后任意非空 event ID 获 test receipt** |
| issuer closed | 不产生 receipt | PASS / fail closed |
| old endpoint after restart | 不可复用 | PASS（closed pair invalid） |

kernel headers 确认 `pidfd_open=434`、`pidfd_getfd=438`；`/proc/sys/kernel/yama/ptrace_scope` 不存在，说明当前 kernel
没有 Yama 限制面。本任务不获授权修改 kernel、systemd sandbox、UID、namespace 或 LSM 配置来规避结果。

## SPIKE-A 至 SPIKE-M

| 场景 | 结果 | 证据结论 |
|---|---|---|
| SPIKE-A `PLUGIN_LOADS_WITHOUT_HERMES_CORE_PATCH` | PASS | project plugin dry-run loader 成功 |
| SPIKE-B `RAW_WECOM_MSGID_VISIBLE_PRE_AGENT` | FAIL / UNPROVEN | 源码位置成立；真实 callback 未在 Stop 后继续 |
| SPIKE-C `TRUSTED_CALLBACK_CAN_USE_CAPABILITY` | PASS | strict synthetic callback frame 获 test receipt |
| SPIKE-D `AGENT_CANNOT_USE_CAPABILITY` | PASS / LIMITED | 普通 child 不继承；不覆盖独立同 UID attack |
| SPIKE-E `TOOL_CHILD_CANNOT_INHERIT_CAPABILITY` | PASS | `close-on-exec` 后 child 看不到 FD |
| SPIKE-F `LOCAL_SHELL_CANNOT_CONNECT_TO_ISSUER` | **FAIL** | same UID `pidfd_getfd` 复制并调用成功 |
| SPIKE-G `NO_NAMED_SIGNER_ENDPOINT_EXISTS` | PASS | 只有 anonymous `socketpair()` |
| SPIKE-H `NO_BEARER_CAPABILITY_EXISTS` | PASS | 无 token/env/argv/path |
| SPIKE-I `ISSUER_UNAVAILABLE_FAILS_CLOSED` | PASS | closed endpoint 无 receipt |
| SPIKE-J `CAPABILITY_RESTART_INVALIDATES_OLD_ENDPOINT` | PASS / HARNESS | old pair 关闭后不可用；未重启真实 Hermes |
| SPIKE-K `NO_BUSINESS_MUTATION` | PASS | mutation 0 |
| SPIKE-L `NO_HERMES_CORE_SOURCE_CHANGE` | PASS | Hermes install/source 未修改 |
| SPIKE-M `FAILED_PLUGIN_NOT_LIVE_DISCOVERABLE` | PASS | live `.hermes/plugins/platforms/wecom` 不存在；prototype 仅存于带双重非产品标记的惰性 fixture |

## R1 失败 prototype 隔离

普通 repository checkout 不再暴露可由 Hermes 自动发现的 WeCom override。保留的 fixture 明确标记
`PILOT_SPIKE_ONLY / NOT_PRODUCT_RUNTIME`；只有测试显式复制到临时 project plugin root 时才参与 loader probe。
攻击 harness、supervisor、issuer stub、gateway probe、FD bootstrap 与 protocol 均保留，以便复现已接受的负面安全事实。

## 禁止边界与最终状态

```text
FINAL_CLASSIFICATION:
UNSUPPORTED

CURRENT_PILOT_DEPLOYMENT:
UNSUPPORTED

OPTION_D:
DESIGN_BASELINE_RETAINED /
PROCESS_ISOLATION_UNRESOLVED /
FULL_IMPLEMENTATION_NOT_AUTHORIZED

FINAL_INDEPENDENT_SECURITY_REVIEW:
PASSED

NEGATIVE_EVIDENCE_BASELINE:
APPROVED

SIGNING_ORACLE_ISOLATION:
NOT_PROVEN / FAILED_IN_REAL_PILOT_OS

FRESH_OWNER_INGRESS_EVIDENCE:
UNSUPPORTED

BRIDGE_IMPLEMENTATION:
NOT_AUTHORIZED

PHASE_1:
NOT_AUTHORIZED

PHASE_2:
NOT_AUTHORIZED
```

未新增 `TrustedIngressEvidence` product runtime、AI-Lab receiver、DB table/migration、MCP confirm、Preview challenge、
Confirmation、Execution、Verification、Canonical Commit 或 UserTask。QUALITY-003、REL-036、版本、Tag、Release 均未启动或修改。
本轮只完成治理状态收口，没有测试 `PR_SET_DUMPABLE`、Yama、不同 UID、systemd sandbox、namespace、seccomp 或 LSM mitigation。
