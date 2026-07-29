# 统一术语表（Terminology Glossary）

## 使用原则

普通叙述优先使用下表的统一中文表达；代码标识、类型名、字段名、API、环境变量和机器状态
保持原文。首次出现时可使用“中文名称（English Term）”，后续不反复切换译法。

| English / Identifier | 统一中文表达 | 使用规则 |
| --- | --- | --- |
| Governance | 治理 | 普通叙述使用“治理” |
| Reconciliation | 治理对账 | 指合并后稳定状态对齐；不得与一般数据同步混用 |
| Planning Baseline | 规划基线 | 状态值保留 `PLANNING_BASELINE` |
| Implementation | 产品实施 / 实施 | 产品范围用“产品实施”；一般步骤可用“实施” |
| Acceptance | 验收 | `ACC-*` 标识和机器状态不翻译 |
| Automated Verification | 自动化验证 | 不得写成人工验收 |
| Manual Acceptance | 人工验收 | 必须有实际人工执行证据 |
| Post-merge Verification | 合并后验证 | 指 merge commit 上的验证 |
| Quality Gate | 质量门禁 | Workflow 与 Job 名称保留 `Quality Gate` |
| Daily Review | 每日复盘 | API、类名和产品能力名可保留 `Daily Review` |
| Daily Agenda | 每日议程 | API、类名和产品能力名可保留 `Daily Agenda` |
| Action Hint | 行动提示 | 字段名和类型名保持原文 |
| Local Daily Profile | 本地日常运行配置 | 环境变量与配置键保持原文 |
| Quiescent Backup | 静止备份 | 首次出现可写“静止备份（Quiescent Backup）” |
| Restore | 恢复 | 命令、函数和状态值保持原文 |
| Workspace | 工作空间 | 统一使用“工作空间”；`WorkspaceKey` 不翻译 |
| Composition Root | 组合根 | 类型名和函数名保持原文 |
| Provider | 模型提供方 / Provider | 普通产品叙述用“模型提供方”；技术边界可保留 |
| FailureInfo | 失败信息合同 / `FailureInfo` | 类型名不翻译 |
| Saga | Saga | 首次出现说明为跨步骤恢复协议 |
| Read Model | 读取模型 | 类名保持原文 |
| EventBus | 事件总线 / `EventBus` | 类型名不翻译 |
| Scheduler | 调度器 / Scheduler | 运行时组件名可保留原文 |
| Reminder | 提醒事项 / Reminder | 领域对象与类型名保留原文 |
| UserTask | 用户任务 / UserTask | 领域对象与类型名保留原文 |
| Waiting-For | 等待项 / Waiting-For | canonical 领域名保留原文 |
| Inbox | 收件箱 / Inbox | canonical 领域名保留原文 |
| Work Log | 工作日志 | ID、类名和 API 字段保持原文 |
| Canonical | 规范对象 / canonical | 技术边界中允许保留小写原文 |
| Fail closed | 失败关闭 | 首次出现可保留英文 |
| Idempotency | 幂等性 | `idempotency_key` 等字段保持原文 |
| Revision | 修订版本 / revision | 字段名和参数名保持原文 |
| Preview / Confirm | 预览 / 确认 | 命令和状态值保持原文 |
| Source of Truth | 权威来源 | 不使用“唯一真相源”等其他译法 |
| Current Product SP | 当前产品 SP | 机器字段 `current_sp` 保持原文 |
| Next Candidate SP | 下一候选 SP | 候选不等于授权或排期 |
| Draft PR | Draft PR | 不译为“草稿合并请求”以避免工具术语漂移 |
| Mergeable | 可合并 | GitHub 机器值 `MERGEABLE` 保持原文 |
| Health / Readiness | 健康检查 / 就绪检查 | 路由和字段保持原文 |
| Background Task | 后台任务 | 类型名和日志保持原文 |
| Data Root | 数据根目录 | 环境变量保持原文 |
| Local-first | 本地优先 | 产品定位统一使用该表达 |
| Single-user-oriented | 面向单用户 | 不扩展为多用户安全承诺 |

## 禁止混用

- 每日复盘不得在普通叙述中写成“回顾”或只写 `Review`；
- 行动提示不得写成“动作提示”；
- 工作空间不得写成“工作区”，但引用历史原文时可保留；
- 静止备份不得写成“冷备份”或“离线备份”；
- 产品实施不得用“实现”代替授权与生命周期含义；
- 治理对账不得写成“状态同步”；
- 自动化验证、人工验收和合并后验证必须分别陈述。

## 差异保留

技术标识中的既有词形不受普通叙述规则影响。例如 `workspace_id`、`DailyReviewService`、
`ActionHint`、`restore()` 和 `NOT_EXECUTED` 必须保持原样。历史标题和原始证据也保持
原文，但应由中文上下文解释。
