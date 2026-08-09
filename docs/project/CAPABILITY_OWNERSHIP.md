# AI-Lab OS 能力所有权

- 战略任务：STRAT-001
- 状态：APPROVED / MERGED / MAIN QUALITY GATE PASSED / POST-MERGE RECONCILED / ARCHIVED
- 日期：2026-08-06

> ARCH-001 当前为 APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED /
> ARCHIVED；RFC-032 为 Adopted，ADR-069～072 为 Accepted。该状态不构成产品实现授权。

## 所有权判定规则

能力所有权不按“哪一层先收到用户输入”划分，而按“哪一层必须对事实、规则、结果和恢复
负责”划分。Agent Shell 可以理解、建议和编排；AI-Lab 必须决定业务写入是否合法、保存
权威状态、记录确认与审批，并验证最终结果。

## Agent Shell 与可信业务核心

| 能力 | Agent Shell 职责 | AI-Lab Business OS 职责 | 边界说明 |
|---|---|---|---|
| 通用对话与 Agent Loop | OWN | 不扩张 | Hermes 为首选实现，但必须可替换 |
| 渠道与消息格式 | OWN | 仅公开 Adapter | 企业微信、Web、语音、桌面不进入业务核心 |
| 通用 Skills 与工具发现 | OWN | 只暴露受控业务能力 | Skill 描述不是业务授权 |
| Browser / Computer Use / 外部动作 | 可作为执行者或编排者 | OWN POLICY / PREVIEW / CONFIRMATION / APPROVAL / AUDIT / STATUS / VERIFY / RECOVERY；正式外部系统 Adapter 可执行 | 执行者可为 Shell、AI-Lab Adapter 或其他受控 Execution Adapter |
| 通用 Cron | OWN | 不复制 | 通用唤醒和投递由 Shell 提供 |
| 业务 Reminder / Scheduler | 可触发、可展示 | OWN | 到期事实、状态、幂等、执行证据与恢复归 AI-Lab |
| 业务对象与规则 | 不拥有 | OWN | Shell 只能通过中立 contract 访问 |
| Preview / Confirmation / Approval | 负责呈现 | OWN | Shell conversation 不能替代持久化审批事实 |
| Audit / Verified Result / Recovery | 可展示 | OWN | Tool response 不是最终成功证明 |
| MCP | 可作为 transport | 可作为 Adapter transport | 不得绕过 Trusted Interaction Boundary |

Hermes 不得直接访问 AI-Lab 数据库。AI-Lab 不得 import、链接或依赖 Hermes 内部模块、
私有数据结构、会话存储或生命周期。Adapter contract 应可由其他 Shell 实现，并通过
contract tests 验证替换性。

实际执行可以由 Agent Shell、AI-Lab 的正式外部系统 Adapter，或其他受控 Execution
Adapter 承担。执行能力所有权与业务行动权威是两件事：无论执行者是谁，AI-Lab 始终
掌握业务 Policy、Preview、Confirmation、Approval、Audit、Status、Verified Result
与 Recovery。

## 数据与记忆所有权

| 信息类型 | 权威所有者 | Shell 可保留内容 | 禁止替代 |
|---|---|---|---|
| 业务事实 | AI-Lab | ID、摘要、临时上下文 | Hermes Memory |
| 业务状态 | AI-Lab | 展示缓存 | Conversation state |
| 业务规则 | AI-Lab | 能力说明 | Prompt 或 Skill 文本 |
| Confirmation | AI-Lab | 呈现确认问题与提交 token | 聊天中的“好的” |
| Approval | AI-Lab | 展示审批状态 | 消息 reaction 或会话记忆 |
| 执行结果 | AI-Lab | Tool response、进度信息 | 未验证的成功文本 |
| 会话记忆 | Agent Shell | 对话摘要、表达偏好 | 业务事实与审批事实 |
| 用户偏好 | Shell 为交互偏好；AI-Lab 为业务规则型偏好 | 非权威个性化 | 价格、权限、审批规则 |
| 决策记忆 | AI-Lab 保存被采纳的业务决策与依据 | 候选推理摘要 | 模型隐式推理 |

跨会话长期记忆不是一个单一存储：Shell Memory 负责“如何继续对话”，AI-Lab 负责“业务上
已经发生什么”。两者发生冲突时，以 AI-Lab canonical fact 为准，并把冲突作为可见失败
或澄清需求处理。

## 企业知识所有权

AI-Lab 拥有企业知识的来源登记、文档版本、审核状态、有效期、引用、撤回和访问规则。
Shell 可以负责文件获取、解析、检索编排和答案表达，但只有 AI-Lab 标记为有效的来源才能
支持业务回答或决策。

以下内容不是企业知识事实：

- Hermes 对话摘要；
- 未登记来源的向量片段；
- 模型自行补全的背景；
- 没有 document version 和 citation 的答案；
- 已过期或已撤回但仍存在于 Shell cache 的内容。

## Interaction 与 Confirmation 边界

可信交互至少区分以下阶段：

```text
View → Preview → Confirm / Cancel → Execute → Status → Verified Result
```

- View：只读 canonical fact，不产生业务写入。
- Preview：由 AI-Lab 根据当前 revision、规则和风险生成；零业务副作用，具有有效期。
- Confirm：用户明确确认同一 preview；AI-Lab 持久化 confirmation fact。
- Approval：高风险或组织性动作的独立授权，可与发起人不同。
- Cancel：终止待确认意图，不伪装成执行失败。
- Execute：只消费有效 confirmation/approval，并使用 idempotency 防止重复执行。
- Status：反映 canonical execution state，不依赖对话是否中断。
- Verified Result：由 AI-Lab 通过自身状态、外部回执或 reconciliation 证明最终结果。

Shell 可以把自然语言映射为 View 或 Preview 请求，也可以呈现 Confirmation，但不得自行
生成已确认状态、复用过期 Preview、隐藏失败或把 timeout 当成功。

## 现有模块处理分类

| 模块 | 分类 | 当前价值 | 重复建设与后续处理 | 兼容风险 |
|---|---|---|---|---|
| Composition Root / SystemContainer | CORE | 唯一装配与生命周期所有权 | 继续作为可信核心装配边界 | Adapter 不得创建第二套核心 |
| FailureInfo | CORE | 统一机器失败语义 | 扩展到 Interaction 与外部执行 | Shell 需稳定映射错误码 |
| DatabaseManager | CORE | SQLite 连接所有权与关闭语义 | 保持 AI-Lab 内部权威 | 禁止 Shell 直连数据库 |
| Workspace | CORE | 当前隔离和上下文边界 | 演进身份/RBAC 前继续使用 | 不得声称强多租户 |
| UserTask | CORE | canonical 任务事实 | 用于真实业务闭环 | 保持 ID/revision 兼容 |
| Reminder / Scheduler bridge | CORE | 持久业务到期与执行状态 | 保留业务调度；通用 Cron 外置 | 区分唤醒投递与业务事实 |
| Inbox / Capture-to-Action | CORE | 模糊输入的持久捕获与解析 | 作为可信自然交互入口基座 | 不让 Shell 会话替代 pending fact |
| Waiting-For | CORE | 客户/外部依赖跟进事实 | v0.37 客户跟进复用 | 领域语义不能退化为通用 task |
| Work Log | CORE | 已发生工作的审计事实 | 继续作为证据与复盘来源 | Episodic 名称不等于 Shell memory |
| Agenda / Daily Review | CORE | 聚合 canonical facts | 作为 View 层继续使用 | 聚合失败必须可见 |
| Action Hints / Review-to-Action | CORE | 确定性下一步映射 | 演进为 Preview 前置，不直接执行 | 不得把 hint 当授权 |
| revision / idempotency / Saga | CORE | 并发、重试和跨库恢复 | 继续用于可信写入 | Adapter 必须透传合同字段 |
| shutdown / restart / backup / recovery | CORE | 本地运行与恢复证据 | 保持并扩大到业务闭环 | 不声称在线一致性备份 |
| EventBus | RETAIN | 内部解耦已有价值 | 仅按真实业务事件激活 | 不成为外部事实源 |
| API / CLI | RETAIN | 已验证入口和诊断能力 | 保持兼容，Adapter 使用公开 contract | 不与 Hermes 专用化 |
| Provider layer | RETAIN | 可选模型访问 | 限定为业务辅助，不建设模型平台 | 模型输出不是事实 |
| Knowledge layer | RETAIN | 已有存储/检索骨架 | v0.38 按审核与引用闭环重激活 | 避免与 Shell RAG 重复 |
| CEO Assistant | FREEZE | 已验证自然语言入口 | 保留兼容，冻结通用助手扩张 | 与 Shell 重合明显 |
| Semantic / Decision Memory 通用扩张 | FREEZE | 有实验基础 | 仅为明确业务知识/决策模型服务 | 避免双重权威 |
| Tool Runtime / MCP 通用扩张 | FREEZE | 有工具适配实验 | 不扩建平台；保留 MCP transport 候选 | 不得绕过确认边界 |
| Workflow Engine | FREEZE | 有状态机与恢复实验 | 仅在具体业务流程证明需要时复用 | 避免通用编排平台化 |
| Generic Task | FREEZE | 历史抽象 | 新业务优先 canonical domain | 与 UserTask 重叠 |
| Session Memory / Conversation | EXTERNALIZE | 通用对话连续性 | 交给 Agent Shell | 不得成为业务/审批事实 |
| Agent Runtime / Agent Loop | EXTERNALIZE | 通用自主循环 | 交给 Hermes 等成熟 Shell | 保持 Adapter 可替换 |
| Channels / Skills / Browser / Computer Use | EXTERNALIZE | 成熟外部生态 | Shell 优先提供 | 高风险动作仍受 AI-Lab 控制 |
| Coordination / 通用 Multi-Agent | EXTERNALIZE | 实验性协作骨架 | 更后续由 Shell 编排、AI-Lab 管业务事实 | 不得共享数据库捷径 |
| `core/agent`、`core/agents` 与顶层 `agents` 重叠 | DEPRECATION_CANDIDATE | 历史兼容 | 后续独立任务评估，STRAT-001 不删除 | 需先清点 import 与公共 API |
| 重复 Knowledge 实现 | DEPRECATION_CANDIDATE | 各自验证过局部能力 | v0.38 前决定 canonical 边界 | 数据迁移与引用兼容风险 |
| Alpha Assistant 与 CEO Assistant 重叠 | DEPRECATION_CANDIDATE | 历史入口 | 在 Shell Adapter 稳定后评估 | 不得提前移除用户入口 |

## 长期能力覆盖矩阵

| 长期能力 | 判断 | 所有权与依赖 |
|---|---|---|
| 个人 CEO 助手 | 部分具备 | Shell 负责自然交互，AI-Lab 负责经营事实 |
| 企业微信入口 | 规划可覆盖 / 需要外部系统 | PILOT-001 渠道接入，不进入核心 |
| 长期记忆 | 部分具备 | 会话记忆归 Shell；业务、决策和证据归 AI-Lab |
| 主动提醒 | 部分具备 | AI-Lab 有业务 Reminder；外部投递与通用唤醒需 Shell |
| 企业知识库 | 部分具备 / 需要新增领域模型 | v0.38 增加 source/version/review/citation |
| 新人培训 | 规划可覆盖 | 基于已审核企业知识和 Shell 交互 |
| 客户跟进 | 部分具备 / 需要新增领域模型 | Waiting-For 可复用，v0.37 增加 Customer/Contact |
| 报价需求收集 | 规划可覆盖 / 需要新增领域模型 | v0.37 Quote Request |
| 自动报价 | 需要新增领域模型 | v0.39 候选，必须版本化和审批 |
| 配方、规格、原料和包装数据 | 需要新增领域模型 | AI-Lab 权威主数据或 ERP 映射 |
| ERP 集成 | 需要外部系统 | AI-Lab 保存映射、意图、审计和 Verified Result |
| 经营分析 | 规划可覆盖 / 需要新增领域模型 | 基于 canonical business facts |
| 工具调用 | 部分具备 / 需要外部系统 | Shell、AI-Lab 正式 Adapter 或受控 Execution Adapter 可执行；AI-Lab 掌握业务控制与验证 |
| Computer Use | 需要外部系统 / 暂不建议实施 | 权限与验证成熟后启用 |
| 多 Agent | 需要外部系统 / 暂不建议实施 | Shell 编排，不新增业务事实源 |
| 自动研发工作流 | 暂不建议实施 | 更后续受控执行与独立审查 |
| 高风险操作审批 | 部分具备 / 需要新增领域模型 | Confirmation 基础可复用，Approval 需明确模型 |
| 审计与恢复 | 部分具备 | FailureInfo、Saga、Work Log、backup/recovery 为基座 |

## 变更约束

本文件只定义规划所有权，不授权删除、弃用、迁移、运行时修改或任何后续任务启动。
