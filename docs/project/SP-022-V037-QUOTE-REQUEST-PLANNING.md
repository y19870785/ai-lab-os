# SP-022 v0.37 报价需求与客户跟进闭环规划基线

> 日期：2026-08-14
> 重建来源：`a8b3392` 规划语义
> 状态：PLANNING_BASELINE_PROPOSED / PENDING_INDEPENDENT_PLANNING_REVIEW / IMPLEMENTATION_NOT_AUTHORIZED / ACC_022_NOT_EXECUTED
> 目标版本：v0.37

## 背景与目标

- 背景：当前 Product SP 为 None，产品处于空窗期；PILOT-001 受进程隔离阻塞，v0.36 的 WeCom Pilot 路线无法短期提供产品增量。
- 目标：建立报价需求与客户跟进闭环，让真实客户请求可从入口进入 AI-Lab，形成可追踪业务对象并闭环到下一行动。
- 优势：纯本地业务闭环，不依赖 process isolation；可复用 Waiting-For、Inbox、Daily Review 边界与 Composition Root。

## 范围

| 项目 | 内容 |
| --- | --- |
| 纳入 | Quote Request、Customer、Contact、Follow-up、Next Action、Audit |
| 不纳入 | 自动价格计算（v0.39 候选）、报价版本与审批（v0.39 候选）、ERP 集成（v0.40 候选）、通用 CRM 平台扩张 |
| 先做 | 需求收集、责任归属、状态推进、人工确认与审计事实 |

## 领域模型草案

| 对象 | 关键字段（草案） | 语义 |
| --- | --- | --- |
| Quote Request | 客户、来源、需求描述、状态、优先级 | 报价需求事实 |
| Customer | 名称、联系方式、workspace | 客户主数据 |
| Contact | 姓名、角色、联系方式、客户 | 联系人事实 |
| Follow-up | 目标、到期、状态、责任 | 复用 Waiting-For 语义 |
| Next Action | 动作、归属、截止 | 闭环到下一行动 |
| Audit | 操作记录、trace、证据 | 审计事实 |

## 交互与边界

- 确定性入口：Inbox capture 到 Quote Request 转换，复用 Unified Inbox 的 CLAIMED 到 TARGET_CREATED 到 COMPLETED 路径。
- LLM 不参与写入判断、字段补猜或成功证明，沿用 SP-017 原则。
- Follow-up 复用 Waiting-For canonical domain；Next Action 显式关联 Quote Request。
- Workspace 逻辑隔离沿用 WorkspaceKey；不引入用户身份与 RBAC。

## 验收与治理计划

| 阶段 | 内容 | 授权要求 |
| --- | --- | --- |
| 规划 | 本规划基线、RFC-034 草案与 ADR-074 至 ADR-075 草案 | Owner 批准规划 |
| 实现 | canonical domain、持久化、API 与 CLI 入口、正式验收 | 单独实现授权 |
| 验收 | ACC-022 场景全通过 | 独立证据复核 |
| 发布 | v0.37 版本、Tag 与 Release | 单独发布授权 |

## 成功标准

- 一个真实客户请求可以从 CLI、API 或 CEO Assistant 入口进入 AI-Lab，形成 Quote Request，并可在 Daily Review 中看到下一行动。
- 全过程可审计、可恢复；任何写操作都经过确定性确认。
- 全量回归零新增失败；真实 Provider 不参与写入路径。

## 相关文档

- [路线图](ROADMAP.md)
- [能力所有权](CAPABILITY_OWNERSHIP.md)
