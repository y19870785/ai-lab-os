# PILOT-001-P1A 内部可信入站确认 Pilot

## 1. 安全分类

本能力仅属于 `PILOT_GRADE_LOCAL_TRUSTED_HOST_PROFILE`：

```text
INTERNAL_TEST_ONLY
LOCAL_TRUSTED_HOST
NOT_PRODUCTION_SECURITY
```

IB-IMP-A 的负面证据保持不变：已测试 WSL2 同 UID topology 可经
`pidfd_getfd` 复制 issuer capability，`SIGNING_ORACLE_ISOLATION` 仍为
`FAILED_FOR_TESTED_TOPOLOGY`，`INGRESS_PROCESS_ISOLATION` 仍为
`UNRESOLVED`。本 Pilot 仅在模型无法启动任意本地进程的前提下，把 hostile
same-UID process 排除在内部测试威胁模型之外。

## 2. 已实现的最小边界

- 默认 `.hermes/plugins/platforms/wecom/` 必须不存在。
- Pilot plugin 只投影到临时 Hermes project，停止后删除。
- WeCom event authority 只接受 `body.msgid`，缺失时不签发 Evidence。
- issuer root 独立持有 Ed25519 private key、event identity key、issuance journal、public key 与
  content binding key；MCP/AI-Lab runtime 只配置独立 verifier projection root。该 projection
  仅包含 retained public verification keys、content binding key、trusted issuer allowlist 与
  operator-provisioned opaque binding config，不包含 issuer root path，也不具备 `issue()`。
- `TrustedIngressEvidenceEnvelopeV1` 使用 RFC 8785/JCS 签名，字段集合固定。
- V1 wire value contract 固定为 `trusted-ingress-evidence/v1`、毫秒精度 UTC `Z`
  时间、`hmac-sha256:<lowercase hex>` 摘要与 `ed25519:<base64url-no-pad>` 签名；
  duplicate/unknown/missing field 与非 canonical value 均 fail closed。
- issuer 以 `evidence_id` 为 key 保存最小 durable issuance journal；同一 event 重投和
  issuer restart 均返回首次 envelope，不刷新时间、不重签，冲突 payload fail closed。
- signing-key rotation 只轮换 active signing key；event identity key、content binding、opaque
  bindings 与 issuance journal 保持稳定。旧 public key 保留在 verifier allowlist；旧 event
  redelivery 仍返回原 key 签发的 exact envelope，新 event 才使用新 active key。
- Preview commit 后由 AI-Lab CSPRNG 生成一次性 challenge。
- Evidence consume、challenge consume、Confirmation fact 与 Interaction CAS
  在同一 SQLite transaction 中完成。
- 成功终点仅为 `AUTHORIZED`；Execution、Verification、UserTask mutation 与
  canonical business commit 均不启动。

## 3. Hermes 模型工具闸门

隔离 profile 必须关闭 Hermes progressive `tool_search`，并把 WeCom platform
toolset 限定为唯一 `ai-lab-p1a` MCP server。Hermes 会为 MCP tool 添加固定
namespace，实际 schema 枚举必须仅包含：

```text
mcp__ai_lab_p1a__ai_lab_interaction_preview
mcp__ai_lab_p1a__ai_lab_interaction_status
mcp__ai_lab_p1a__ai_lab_interaction_view
mcp__ai_lab_p1a__ai_lab_interaction_confirm
```

正式 `start-gateway` 路径先创建临时 profile，再调用已安装 Hermes 自身的 MCP discovery、
WeCom platform toolset resolution 与 model schema resolver。只有 actual namespace 通过
exact four-tool assertion 后才执行 `python -m gateway.run`。底层 MCP contract 名仍精确为
任务书规定的四个 `ai_lab_interaction_*` 名称。
任何 `terminal`、`process`、文件写入、browser、generic code execution、
`tool_search/tool_call` 或额外 AI-Lab tool 出现时，必须停止为
`INTERNAL_PILOT_TOOL_ISOLATION_UNPROVEN`。

## 4. 自动验收映射

| 场景 | 验证目标 |
|---|---|
| P1A-A | 默认 live Pilot plugin 不存在 |
| P1A-B | Hermes/MCP 工具面恰好四个 |
| P1A-C | 模型无任意本地进程启动工具 |
| P1A-D | 只接受 `body.msgid`，相同 event identity 稳定 |
| P1A-E | challenge 由 AI-Lab 在 Preview 后生成 |
| P1A-F | Message A Evidence 不能越过 Preview/challenge 自确认 |
| P1A-G | 合法 Message B 只创建一个 Confirmation |
| P1A-H | Evidence 单次消费，replay 不增加 Confirmation |
| P1A-I | wrong Owner/conversation/challenge/text/revision 全部拒绝 |
| P1A-J | 相同 `body.msgid` 的 `evidence_id` 稳定 |
| P1A-K | consumption 持久化，不依赖进程内 cache |
| P1A-L | UserTask mutation 为 0 |
| P1A-M | real Provider call 为 0 |
| P1A-N | verifier 不加载 issuer private/identity key 且不能 mint Evidence |
| P1A-O | 同一 event redelivery 返回首次 exact envelope，冲突 payload 拒绝 |
| P1A-P | issuance journal 跨 issuer restart 返回首次 exact envelope |
| P1A-Q | signing-key rotation 后旧 event 返回原 envelope，旧/新 key 均可验证 |

R1 还覆盖 exact schema 对 unknown、missing、duplicate JSON field、wrong version、非 canonical
timestamp、错误 digest 与 signature encoding 的拒绝。opaque binding 由 operator 执行 key
bootstrap 时随机 provision，不从 raw account/Owner/conversation ID 派生。

## 5. 真实 WeCom 验收状态

第一次 2026-08-13 单 Owner WeCom 结果属于
`PRE_R1_REAL_EVIDENCE / CONTRACT_IMPLEMENTATION_REVISED`。它证明真实 Message A/B、
Preview/challenge/Confirmation/atomic consume 与零业务 mutation 链路，但发生在 R1 strict
wire contract、key split、issuance journal 与正式 startup gate 合入前；不得作为 R1 wire
compatibility 的真实实测声明。脱敏历史结果如下：

```text
Security profile: PILOT_GRADE_LOCAL_TRUSTED_HOST_PROFILE
Message A: PASS
Message A evidence: VERIFIED / UNUSED
Interaction: int_4ca06aa2ad8647b29cfb4d103a33d976
Preview: prv_0932c5f5ec764949bcb8b781abd7380a / revision 1
Canonical due_at: 2026-08-14T07:00:00+00:00
Owner local presentation: 2026-08-14 15:00 Asia/Shanghai

Expired challenge attempt: DENIED / evidence UNUSED
Wrong challenge text attempt: DENIED / evidence UNUSED
Fresh Message B: PASS
Consumed evidence: tie_pd2gl6aysreqgmtfb4g36f7lps27swz6onq7v7z5nokmuojaiolq
Consumed challenge: pch_d2cdd54ae46bc52714ac36602fc866db
Confirmation: cnf_a3d33c51adea49f99fa6aab401948df3
Interaction final state: AUTHORIZED / revision 3
Execution: NOT_STARTED
UserTask: 3 -> 3
AI-Lab Real Provider: 0
```

R1 修改会影响实际 Hermes startup/tool profile 与 Evidence wire compatibility，因此按任务书
执行了一次新的内部 Message A/B 复验，但仍未创建 UserTask 或进入 Execution。脱敏结果如下：

```text
R1 Real Revalidation: PASSED
Hermes actual model namespace: EXACT FOUR TOOLS
WeCom Pilot gateway after gate: CONNECTED
Message A: PASS
Interaction: int_c979c1675b824dcc81ff42b59650f9a3
Preview: prv_6cd1b1da98de4cd29bed8b4814efb552 / revision 1
Canonical due_at: 2026-08-14T07:00:00+00:00
Owner local presentation: 2026-08-14 15:00 Asia/Shanghai

Message B: PASS
Evidence version: trusted-ingress-evidence/v1
Timestamp wire: UTC / millisecond precision / Z
Opaque bindings: acct_ / owner_ / conv_
Content digest: hmac-sha256:<lowercase hex>
Signature: ed25519:<base64url without padding>
Evidence verification: VERIFIED
Evidence consumption: CONSUMED
Confirmation: cnf_1948eb2a1198445cb0f3318022b9ce7b
Interaction final state: AUTHORIZED / revision 3
Canonical object: null
Execution: NOT_STARTED
UserTask: 3 -> 3
AI-Lab Real Provider: 0
```

R1-REV1 将 MCP/AI-Lab verifier 改为独立 material projection root，并增加 signing-key rotation
兼容性，因此再次执行一次真实内部 Message A/B 复验。第一次自然语言 Message A 因模型未能
推断严格 UserTask schema 而被 policy 拒绝，未生成 Interaction、Confirmation 或 UserTask；
随后使用明确的五字段 acceptance input 完成有效复验。该输入修正不属于安全边界降级。

```text
R1-REV1 Real Revalidation: PASSED
Hermes actual model namespace: EXACT FOUR TOOLS
MCP issuer root configured: NO
MCP verifier projection root configured: YES
Verifier projection forbidden material: ABSENT
WeCom Pilot gateway after gate: CONNECTED
Initial ambiguous Message A: INVALID_ACCEPTANCE_INPUT / ZERO MUTATION
Valid Message A: PASS
Interaction: int_8d9a16d7e8014ea9ad03abe4c655d063
Preview: prv_2afc9304157b4b12b4bd9d46c5c814a4 / revision 1
Canonical due_at: 2026-08-14T07:00:00+00:00
Owner local presentation: 2026-08-14 15:00 Asia/Shanghai

Fresh Message B: PASS
Evidence: tie_szo5d6hbx25lbjggkzmvuiyhteyrangyriy72rnpblgqkin6xygq
Evidence version: trusted-ingress-evidence/v1
Timestamp wire: UTC / millisecond precision / Z
Opaque bindings: acct_ / owner_ / conv_
Content digest: hmac-sha256:<lowercase hex>
Signature: ed25519:<base64url without padding>
Evidence verification: VERIFIED
Evidence consumption: CONSUMED
Confirmation: cnf_3d40a10b45034774934035251476733b
Interaction final state: AUTHORIZED / revision 3
Canonical object: null
Execution: NOT_STARTED
UserTask: 3 -> 3
AI-Lab Real Provider: 0
```

R1 现场启动还验证了默认 Hermes 在临时 Pilot 结束后恢复为 `active`，其
`WorkingDirectory` 与 `HERMES_HOME` 均保持 `/home/hechao/.hermes`。临时 project 与临时
进程已经移除；默认 live `.hermes/plugins/platforms/wecom` 仍不得存在。

第一次预验收启动曾遗漏 nested project plugin 的显式 opt-in，canonical evidence 数为
`0`，因此该轮被判为无效并停止；未创建 Confirmation 或 UserTask。修订后临时 profile
显式启用 `platforms/wecom`，现场注册模块为
`hermes_plugins.platforms__wecom.adapter`，并新增回归测试防止 bundled adapter 静默回退。
同时发现 `hermes gateway run` 会自刷新已安装 systemd unit，并把临时 `HERMES_HOME`
写入 live service。该 unit 已恢复为 `/home/hechao/.hermes` 且验证为 `active`；launcher
现固定使用 Hermes venv Python 直接执行 `python -m gateway.run`，绕过 service-refresh
CLI 路径，临时 Pilot 不再改写默认 service。

第一次有效确认消息到达时 challenge 已过期，AI-Lab 返回
`trusted_confirmation.validation_denied`，Evidence 保持 `UNUSED`。随后 AI-Lab 轮换新
challenge；拼错文本再次被拒且 Evidence 未消费。最终精确的新 Owner 消息在 Preview
之后到达，Evidence、challenge、Confirmation 与 Interaction CAS 在同一事务中消费并
提交。该历史结果只升级为 `INTERNAL_PILOT_TRUSTED_CONFIRMATION_PROVEN`。R1 进一步通过
自动化与一次新的真实内部复验关闭 canonical contract、authority boundary、actual startup
namespace 与 wire compatibility 证据。最终独立审查、PR #77 Squash Merge、main Quality Gate
`31719553362 / SUCCESS` 与独立 Post-Merge Verification 均已通过；最终合并提交为
`1daf52ee500d5dc79ba1fc632f240ddf756bb93b`，唯一父提交为
`89aaab92320f1541cabd36d5ef8d7b69b0f450e4`。P1A 进入 self-closing 治理对账，合并后归档。

## 6. 合并后治理对账

- 对账任务：`PILOT-001-P1A-POST-MERGE-RECONCILIATION`
- 类型：`DOCUMENTATION / GOVERNANCE ONLY`
- Canonical Base：`1daf52ee500d5dc79ba1fc632f240ddf756bb93b`
- Feature PR：`#77 / MERGED`
- Approved Head：`4a59e65b80bc98b1032a051c176ad8d50c343879`
- Squash Merge Commit：`1daf52ee500d5dc79ba1fc632f240ddf756bb93b`
- Unique Parent：`89aaab92320f1541cabd36d5ef8d7b69b0f450e4`
- Main Quality Gate：`31719553362 / SUCCESS`
- Independent Post-Merge Verification：`PASSED`
- 生效规则：本 Draft PR 经独立治理审查、Owner 授权并合并进入 `main` 后，本记录自动成为
  PILOT-001-P1A 最终权威对账与封存记录。
- 递归规则：`SELF_CLOSING / NO_RECURSIVE_RECONCILIATION`。

```text
PILOT-001-P1A:
APPROVED /
MERGED /
MAIN_QUALITY_GATE_PASSED /
FINAL_INDEPENDENT_REVIEW_PASSED /
POST_MERGE_VERIFIED /
RECONCILED /
ARCHIVED

SIGNING_ORACLE_ISOLATION:
FAILED_FOR_TESTED_TOPOLOGY

PROCESS_ISOLATION:
UNRESOLVED

BRIDGE_IMPLEMENTATION:
NOT_AUTHORIZED

PHASE_1_FULL:
NOT_AUTHORIZED

PHASE_2:
NOT_AUTHORIZED

REAL_BUSINESS_MUTATION:
NOT_AUTHORIZED

Execution:
NOT_STARTED
```

该对账不修改产品代码、测试实现、Schema、Migration、dependency、Version、Tag 或 Release，
也不自动创建或授权 PILOT-001 的下一阶段。`current_sp`、`current_governance_task` 与
`current_work` 保持 `null`。

## 7. 长期禁止结论

本 Pilot 不得写成 `PRODUCTION_READY`、`ENTERPRISE_READY`、
`GENERAL_TRUSTED_INGRESS_SUPPORTED` 或 `PROCESS_ISOLATION_RESOLVED`。
`PHASE_1_FULL`、Phase 2 与真实业务 mutation 均未授权。
