# AI-Lab Known Limitations

> 当前版本：`0.33.0` | main：`22f85db16a43e7d09a903859a26ac6a310370d81` | 对账日期：2026-07-19

## 功能与数据限制

| 限制 | 当前说明 |
|---|---|
| 无完整多用户产品能力 | Workspace 边界已存在，但没有用户身份、RBAC 或强多租户隔离 |
| 仅本地存储 | 主要使用 SQLite 与 Chroma，没有跨设备或分布式存储后端 |
| Reminder 外部通知未实现 | 当前提供持久化状态、调度与查询，不代表邮件、短信或推送已送达 |
| Coordination 未接入所有主路径 | 十一层架构中的 Coordination 已独立存在，但部分能力仍默认关闭或未接入 CEO Assistant 主路径 |
| Knowledge / Agent 产品闭环未完成 | Knowledge 主链路、完整 Agent Runtime 产品闭环、自动 Tool Calling 与完整 MCP 闭环仍未完成 |

## 安全限制

| 限制 | 当前说明 |
|---|---|
| 静态单一 Bearer Token | API 鉴权已实现且默认启用，但没有 OAuth、JWT、用户身份或 RBAC；token 轮换需要重启 |
| CORS 不是身份隔离 | 当前使用显式 allowlist 与默认 deny-all，但这不能替代强租户与用户授权模型 |
| 无内建 TLS 终止 | 本地服务使用 HTTP；网络部署需要受控反向代理与 TLS |
| Prompt 注入防护不完整 | 仍需为自然语言输入、知识内容与工具执行建立更强信任边界 |

## 稳定性与部署限制

| 限制 | 当前说明 |
|---|---|
| Long-running 验证有限 | 长时间运行、恢复与资源回收仍缺少完整持续验证 |
| Docker 未完整实测 | 配置存在，但尚无当前基线的受控 build + run 记录 |
| SQLite 并发上限 | 单机持久化不等于高并发或分布式一致性 |
| Windows 编码差异 | PowerShell/CMD 中文管道需要持续保留平台测试 |
| Scheduler 测试时序波动 | PR #33 首次 pytest attempt 曾短暂观察到 Job 状态为 `running`；唯一重跑通过，未涉及 SP-014B 修改文件，需留待独立稳定化范围处理 |

## 质量门禁限制

| 限制 | 当前说明 |
|---|---|
| CI-002 | `tests/real/conftest.py` 的 collection hook 作用域需修复；普通门禁显式使用 `--ignore=tests/real` |
| QUALITY-001 | GitHub Ruff 只检查本次变更的 Python 文件；尚未建立并清理全库历史 Ruff 基线 |
| Real tests 不属于普通门禁 | Quality Gate 不配置真实密钥、不调用外部模型，也不证明 real 测试通过 |
| 平台统计不同 | Ubuntu CI 为 `1096 passed, 6 skipped, 27 warnings`；Windows 本地可运行六个 batch-script 测试，统计可不同 |
