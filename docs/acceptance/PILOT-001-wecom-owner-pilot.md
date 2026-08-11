# ACC-PILOT-001 — 企业微信 Owner 可信任务捕获验收计划

> 状态：PLANNED / 0 EXECUTED / REAL_PILOT_NOT_STARTED
> 授权：IMPLEMENTATION_NOT_AUTHORIZED / PHASE_0_NOT_AUTHORIZED / PHASE_1_NOT_AUTHORIZED / PHASE_2_NOT_AUTHORIZED
> 目标：PILOT-001 / WeCom Owner Trusted Task Capture

## 1. 证据分层

验收必须分别保存以下五类证据，不能相互替代：

| 证据类别 | 证明内容 | 不能证明 |
|---|---|---|
| Automated Evidence | 合同、策略、状态机、幂等、redaction 与负向行为 | 真实 WeCom/Hermes 可用 |
| Real Integration Evidence | 真实 WeCom → Hermes → stdio MCP → AI-Lab 进程链 | Owner 理解并确认准确 Preview |
| Manual Owner Evidence | Owner 看见、修改/取消/确认 Preview 与最终结果 | 重启持久性或幂等 |
| Restart Evidence | 重启后 Interaction、UserTask 与证据仍可定位 | 错误身份被拒绝 |
| Negative Evidence | fail-closed、无 execute/approve tool、uncertain 不重执行 | 正向真实闭环完成 |

单元测试、mock MCP 或本地 JSON-RPC success 不等价于真实企业微信 Pilot 通过。

## 2. 环境与安全前置条件

- AI-Lab 使用 Python 3.12 与 `AI_LAB_PROVIDER_MODE=mock`；
- `OPENAI_API_KEY=DISABLED`、`AI_LAB_LLM_API_KEY=DISABLED`，不得使用空字符串；
- Hermes 可使用其独立真实 Provider 配置，但密钥不得进入 AI-Lab、证据包或日志；
- Pilot Binding Config 明确固定 actor、Workspace、expected shell/channel/WeCom identity；
- 单 Owner、企业微信私聊、本地主机、allowlist、纯文本；
- 记录 AI-Lab Head、Hermes version、MCP SDK version、时间、timezone 与脱敏配置摘要；
- 每一 Phase 开始前具有独立授权；前一 Phase 未通过时不得推进。

## 3. Phase 0 — 传输与身份冒烟（Transport / Identity Smoke）

Phase 0 使用真实 WeCom、Hermes 与 AI-Lab，但禁止 UserTask write。

| ID | 场景 | 预期 | 证据 |
|---|---|---|---|
| P0-01 | Hermes 真实进程启动 AI-Lab stdio MCP | Server 正常启动 | 进程与时间戳日志 |
| P0-02 | Protocol Negotiation | 协商成功，无私有 hack | client/server version 摘要 |
| P0-03 | `tools/list` | 精确返回七项 allowlisted tools | 原始脱敏响应 |
| P0-04 | Tool Schema | Preview/Status schema 可被 Hermes 解析 | schema digest |
| P0-05 | Owner DM Preview | 返回 canonical Preview，`final=false` | Interaction/Preview ID |
| P0-06 | Status | 返回同一 canonical Interaction | status 投影 |
| P0-07 | Clean Shutdown | client/server 正常退出 | exit code 与日志 |
| P0-08 | wrong shell/channel/identity | DENIED / fail closed | `FailureInfo` |
| P0-09 | default/no binding | DENIED，不回退 Workspace | `FailureInfo` |
| P0-10 | business mutation guard | UserTask 计数与数据库事实不变 | 前后 read-only 证据 |

任何 compatibility 失败均 STOP / REPORT；不得现场改依赖或降级安全字段。

## 4. Phase 1 — 真实 Preview-Only

使用真实 Owner、WeCom、Hermes 与业务语言，ExecutionPort 继续 disabled。

| ID | 场景 | 预期 |
|---|---|---|
| P1-01 | “明天下午 3 点跟进 XX 客户的 5000 盒护发精油报价。” | Preview title/due_at/timezone/priority 准确 |
| P1-02 | Owner 修改时间 | 生成新 Preview revision，旧 Preview 与旧 consent 失效 |
| P1-03 | Owner 取消 | Interaction 安全进入 CANCELLED，无 UserTask write |
| P1-04 | 模糊时间 | 明确拒绝或请求修正，不猜测写入 |
| P1-05 | unsupported operation | DENIED，无新 domain 或业务写入 |
| P1-06 | Owner 观察可理解性 | Owner 能复述即将创建的对象与时间 |

Manual Owner Evidence 必须记录 Owner 对 title、description、due_at、timezone、priority 的逐项判断；
Phase 1 通过前 Phase 2 保持 `NOT_AUTHORIZED`。

## 5. Phase 2 — 第一条真实 Canonical Mutation

唯一正向案例：

```text
Owner 在企业微信私聊：
“明天下午 3 点跟进 XX 客户的 5000 盒护发精油报价。”
```

验收步骤与预期：

1. Hermes 收到真实 DM 并生成 provisional `UserTask` proposal；
2. AI-Lab Resolver 从固定配置得到 Owner actor 与 Workspace；
3. Policy Resolver 只解析为 `user_task.create`；
4. Canonical Preview 显示准确 title、due_at、timezone 与 priority；
5. Owner 明确 Confirm exact Preview；
6. Hermes 没有也不调用 execute tool；
7. AI-Lab 内部 Coordinator 调用 `start_execution()`；
8. ExecutionPort 只调用一次 `UserTaskService.create()`；
9. `task_id` 等于规定 deterministic hash；
10. VerificationPort 独立 read-back UserTask；
11. read-back 的 Workspace、title、due_at、priority、source 与 metadata 全部匹配；
12. Canonical Commit Authority 独立确认持久事实并形成 evidence；
13. Interaction 只有在 VerifiedResult 与 required Commit Evidence 存在时进入 `SUCCEEDED`；
14. Shell 结果投影包含 canonical task ID/revision 与 verified result；
15. AI-Lab 重启后 UserTask 仍存在，Interaction 仍为 `SUCCEEDED`；
16. 使用相同 Interaction / idempotent request 再次请求，不产生第二个 UserTask。

任一步无证据均不能记为 PASSED。

## 6. 自动化证据（Automated Evidence）

后续实现至少覆盖：

- Binding Resolver 固定配置与 mismatch fail-closed；
- Operation Policy 精确 allowlist 与 Shell 不可设置权威字段；
- Preview 零业务写、Modify 使旧 consent 失效；
- deterministic ID 同 Interaction 恒定，不同 Interaction 可区分；
- ExecutionPort 只依赖 `UserTaskService`，create 调用最多一次；
- VerificationPort 独立 read-back，不信任 execution return；
- Canonical Commit Authority 只读并验证，不执行写入；
- restart 后仅凭 interaction/workspace/deterministic ID 验证；
- `RECOVERY_REQUIRED` 不重执行；
- AdapterResponse additive projection 不伪造结果；
- secrets redaction 与禁止 credential persistence；
- exact MCP allowlist 与 `final` terminality 语义。

自动证据记录命令、exit code、passed/skipped/warnings、Head SHA 与测试文件位置。

## 7. 真实集成证据（Real Integration Evidence）

必须来自真实 Hermes Process 与真实企业微信 Owner 私聊，至少包含：

- WeCom message receipt 的脱敏 correlation，不含完整消息或 credential；
- Hermes 与 AI-Lab MCP startup、negotiation、`tools/list`、schema digest；
- Preview/Status 调用的 request ID、trace ID、Interaction ID 与 revision；
- Confirm 后无 Shell execute/verify/commit call 的证据；
- AI-Lab 内部 execution/verification/commit transition audit；
- Clean Shutdown 与真实进程 exit code。

不得把 mock client、单元测试或手工构造 JSON 归为 Real Integration Evidence。

## 8. Owner 手工证据（Manual Owner Evidence）

Owner 手工签认至少包括：

- 消息确实来自其企业微信私聊；
- Preview 标题、时间、时区、优先级准确；
- 知道 Confirm 会创建 UserTask；
- Modify 后旧确认无效；
- Cancel 不创建任务；
- 最终结果中的 task ID 可在 AI-Lab 中查询；
- Pilot 未发送客户消息、未生成报价、未创建 Customer/Quote 数据。

证据只记录结论、时间、Interaction ID 与签认人固定 actor ID，不保存完整聊天或凭据。

## 9. 重启证据（Restart Evidence）

1. 记录 `SUCCEEDED` Interaction、deterministic task ID、revision 与 evidence IDs；
2. 正常关闭并重启 AI-Lab；
3. 通过 Status/View 读取同一 Interaction；
4. 通过 `UserTaskService` 读取同一 Workspace 下的同一 task ID；
5. 核对 Preview 字段、source、metadata 与 canonical revision；
6. 再次触发相同幂等请求，确认没有第二条 UserTask；
7. 模拟 execution outcome 落库前的不确定路径，只允许 verify/recover，不允许 reexecute。

## 10. 负向证据（Negative Evidence）

| 场景 | 预期 |
|---|---|
| Wrong Channel | DENIED |
| Wrong Shell | DENIED |
| Wrong WeCom Identity | DENIED |
| No Pilot Binding | DENIED |
| No Operation Policy | DENIED |
| Unsupported Operation | DENIED |
| Stale Preview | DENIED |
| Wrong Preview Revision | DENIED |
| Expired Preview | DENIED |
| Modified Preview + Old Confirmation | DENIED |
| Shell attempts execute | NO SUCH TOOL |
| Shell attempts approve | NO SUCH TOOL |
| Shell 声称“任务已完成” | NO CANONICAL EFFECT |
| Execution outcome uncertain | RECOVERY_REQUIRED |
| Recover | NO REEXECUTION |
| Cross Workspace access | DENIED |
| Duplicate request | SAME TASK / NO DUPLICATE |
| Missing VerifiedResult | NOT SUCCEEDED |
| Missing required Commit Evidence | NOT SUCCEEDED |

每项保留 FailureInfo code/category、canonical state 与业务对象计数/read-back；不得保存 secret 或完整聊天。

## 11. 回滚与停用验收

- 移除 allowlist 或禁用 Pilot flag 后，新 Preview/Execution fail closed；
- 已有 Interaction 的 Status/Audit 仍可读取；
- 停用不会删除 UserTask、Interaction 或 Evidence；
- 停用不会自动取消、补偿或重建业务对象；
- 重新启用前必须重新通过 binding/policy/compatibility gate。

## 12. 最终通过门禁

只有以下条件全部满足才可声明 PILOT-001 通过：

```text
Phase 0 PASSED
Phase 1 PASSED + Manual Owner Evidence
Phase 2 PASSED
Automated Evidence COMPLETE
Real Integration Evidence COMPLETE
Restart Evidence COMPLETE
Negative Evidence COMPLETE
SUCCEEDED + VerifiedResult + required CanonicalCommitEvidence
0 duplicate UserTask
0 credential leak
Independent Acceptance Review PASSED
```

当前结果固定为：

```text
PLANNED: YES
EXECUTED: 0
PASSED: 0
REAL PILOT: NOT STARTED
PHASE 2 IMPLEMENTATION AUTHORIZED: NO
```

## 13. 当前 Stop Point

本文件是验收计划，不是验收证据。Planning PR 完成后必须 STOP，等待独立规划审查；不得配置 Hermes、
连接企业微信、运行真实 Phase、实现 Ports/Coordinator、转 Ready 或 Merge。
