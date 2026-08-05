# AI-Lab 已知限制

> 当前源码版本：`v0.35.0` Alpha / GitHub Pre-release Published | 更新日期：2026-08-06

`v0.35.0` 的发布不改变以下产品限制；REL-035 已最终对账并封存，当前 Governance Task
为 STRAT-001，下一 Product SP 尚未批准。
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
| Agent Shell Adapter 未实现 | Hermes 只是首选候选；当前没有接入、contract test 或替换性证明 |
| Trusted Interaction Boundary 未实现 | View / Preview / Confirm / Cancel / Status / Verified Result 仍需 ARCH-001 定义 |
| Approval 不是完整领域模型 | 现有局部 confirmation 不能被描述为通用高风险审批能力 |
| 企业微信 Owner Pilot 未开始 | 渠道、身份映射、消息可靠性和人工验收均未执行 |
| PR #62 已冻结 | 保持 Open / Draft；不能作为 SP-021 启动或实现授权 |
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

完整机器可读技术债清单以 `project_state.json` 为准。
