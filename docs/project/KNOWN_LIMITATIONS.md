# AI-Lab 已知限制

> 当前源码版本：`v0.35.0` Alpha / GitHub Pre-release Published | 更新日期：2026-08-12

`v0.35.0` 的发布不改变以下产品限制；REL-035 与 STRAT-001 均已最终对账并封存，当前
Current Product SP 与 Governance Task 均为 None；当前工作为 PILOT-001-IBD。P0-R 已实现并通过最终独立审查，Preview authority 已建立；Fresh Owner Ingress Evidence 仍为 `UNSUPPORTED`。可信入站证据桥仅处于 Proposed 设计草案与独立规划审查前状态，尚未实现。SP-021 已通过最终独立审查、合并、main Quality Gate、
ACC-021 最终验收与治理对账，并已封存。
该 Alpha Pre-release 仍不是 production-ready、enterprise-ready、stable release 或
general availability。

## 产品与数据边界

| 限制 | 当前事实 |
|---|---|
| 非完整多用户产品 | 有 workspace 边界，但没有用户身份、RBAC 或强多租户隔离 |
| 本地优先持久化 | 主要使用 SQLite 与可选 Chroma，没有跨设备或分布式存储后端 |
| Reminder 无外部通知 | 当前只有持久化状态、调度与站内查询，不代表邮件、短信或推送已送达 |
| Reminder 时间解析是确定性子集 | 不支持后天、星期、相对/模糊时间、中文分钟、Recurring Reminder 或 LLM 时间解析 |
| Knowledge 产品闭环未完成 | Reindex、Chunk Persistence、Citation 与真实主链路仍缺失 |
| Coordination 默认关闭 | 独立能力存在，但未接入 CEO Assistant 主链路 |
| 无 Web UI | 当前主要入口是 API、CLI 与 CEO Assistant |
| Daily Review 查询范围有限 | 正式 CLI、API 与 CEO Assistant 已复用唯一只读服务，但 review date 只支持 `today` / `yesterday`，不是任意日期分析引擎 |
| Local Daily Profile 不是部署平台 | Windows Local Daily Profile 已实现并通过 ACC-020；它要求显式绝对路径和完整配置，不等于 Docker/服务管理/生产部署认证 |
| Action Hint 是确定性子集 | Action Hints 已实现并通过 ACC-020；只基于 canonical facts/IDs，不使用 LLM 自动选工具或猜测写入意图 |
| 非 Local Daily Profile 的默认路径不稳定 | 默认 data root 仍随 working directory 推导；正式 Local Daily Profile 已验收并要求源码 checkout 外的稳定绝对路径 |
| 在线跨库备份不受支持 | 多个 SQLite 文件与可选 Chroma 只规划停机后的完整 data directory 备份，不承诺在线一致快照 |

## 安全边界

| 限制 | 当前事实 |
|---|---|
| 静态单一 Bearer Token | 无 OAuth、JWT、用户身份或 RBAC；Token 轮换需要重启 |
| CORS 不是身份隔离 | 显式 allowlist / 默认 deny-all 不能替代授权模型 |
| 无内建 TLS 终止 | 网络部署需要受控反向代理和 TLS |
| Prompt 注入防护不完整 | 自然语言、知识内容与工具执行仍需更强信任边界 |

## STRAT-001 规划限制

| 限制 | 当前事实 |
|---|---|
| Agent Shell 真实接入未实现 | INT-001 Draft 已实现 Shell-neutral Adapter、Reference authorities、MCP stdio projection 与替换性自动证据；真实 Hermes、Channel、身份绑定与 operation policy 未接入 |
| Trusted Interaction 外部闭环未完成 | SP-021 已实现 canonical Domain；INT-001 Draft 只投影 Preview/Modify/Confirm/Cancel/Status/View/Recovery，不提供 execute/verify/commit authority 或真实外部动作 |
| 强 Identity / Workspace mapping 未实现 | 当前 bearer token 与 header/profile scope 不能证明 Channel User、Owner、Operator 或 Approver；Pilot 前必须 fail closed |
| Interaction recovery 尚无自动 worker | SP-021 已持久化 Interaction / Execution / Verification / Recovery 并提供显式 recover；未实现 poll/webhook/background reconciliation |
| Approval 尚无完整 Policy/RBAC | SP-021 将 Approval 与 Confirmation 分离并持久化，但正式 Policy engine、角色目录与多主体审批不在本 SP |
| 企业微信 Owner Pilot 仅到 Preview | P0-E 已完成复验，P0-R 已实现并通过最终独立审查，本地单 Owner Preview authority 已建立；该 static binding 不是生产身份认证。Vanilla Hermes 未把 channel-originated event metadata 以模型不可伪造的旁路传给 AI-Lab，Fresh Owner 入站证据仍为 `UNSUPPORTED`。PILOT-001-IBD 只提出模型前 issuer、AI-Lab 验签与持久化单次消费的 Proposed 设计，等待独立规划审查；Bridge implementation 与 Phase 1 未授权 |
| PR #62 已关闭且被取代 | 保留分支、commit、discussion 与历史设计证据；Implementation 从未获授权 |
| 通用平台扩张已冻结但未删除 | Agent/Tool/Workflow/Coordination 重叠代码仍存在，弃用需要独立审计与授权 |

## 稳定性与质量边界

| 限制 | 当前事实 |
|---|---|
| 长时间运行验证仍有限 | ACC-020 已验收受控持续运行、shutdown、restart、静止备份和隔离恢复；这不等于长期压力、高并发或高可用基线 |
| Scheduler shutdown 仅覆盖当前受控边界 | 当前 `SystemContainer` 的同一关闭流程会两次调用 Scheduler shutdown；重复 shutdown、partial-start rollback 与 restart recovery 已通过 SP-020/ACC-020，多进程协调和高可用仍不在范围内 |
| Docker 未正式验证 | 配置存在，但没有当前版本受控 build + run 记录 |
| SQLite 并发上限 | 单机持久化不等于高并发或分布式一致性 |
| Scheduler 测试时序波动 | PR #33 首次 pytest attempt 曾短暂看到 `running`，唯一重跑通过；未在 SP-014B 或 SP-015 修改 Scheduler |
| QUALITY-001 | GitHub Ruff 只检查变更 Python 文件，尚无全仓历史清零基线 |
| Real tests 不属于普通门禁 | Quality Gate 不配置真实密钥，也不调用外部模型 |
| QUALITY-003 Candidate — DeepSeek Real Brief Contract Audit | `test_deepseek_brief → daily_review.date_invalid`；2026-08-09 accidental reproduction；CANDIDATE / NON_BLOCKING / REAL_PROVIDER_ONLY / NOT_STARTED / NOT_AUTHORIZED |
| QUALITY-004 — Real-Provider Credential Isolation Guard | 已确认并修复普通或显式路径 pytest 因 import-time `load_dotenv()` 重新装载本机凭据的风险；双因素 Guard 已实现并通过最终独立安全审查，状态为 RESOLVED / IMPLEMENTED / FINAL_INDEPENDENT_REVIEW_PASSED / REAL_PROVIDER_ISOLATION_GUARD_ESTABLISHED / PILOT_SAFETY_BLOCKER_CLEARED。P0-E 已完成 QUALITY-004 后复验；这不是 WeCom/MCP compatibility failure |

完整机器可读技术债清单以 `project_state.json` 为准。
