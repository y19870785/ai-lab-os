# AI-Lab Known Limitations

> 当前源码版本：`v0.34.0` Alpha Candidate | main 基线：`57444274abd4e568a6af72b218d50290de563654` | 更新日期：2026-07-20

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

## 安全边界

| 限制 | 当前事实 |
|---|---|
| 静态单一 Bearer Token | 无 OAuth、JWT、用户身份或 RBAC；Token 轮换需要重启 |
| CORS 不是身份隔离 | 显式 allowlist / 默认 deny-all 不能替代授权模型 |
| 无内建 TLS 终止 | 网络部署需要受控反向代理和 TLS |
| Prompt 注入防护不完整 | 自然语言、知识内容与工具执行仍需更强信任边界 |

## 稳定性与质量边界

| 限制 | 当前事实 |
|---|---|
| 长时间运行验证有限 | 恢复、资源回收和持续运行仍缺完整基线 |
| Docker 未正式验证 | 配置存在，但没有当前版本受控 build + run 记录 |
| SQLite 并发上限 | 单机持久化不等于高并发或分布式一致性 |
| Scheduler 测试时序波动 | PR #33 首次 pytest attempt 曾短暂看到 `running`，唯一重跑通过；未在 SP-014B 或 SP-015 修改 Scheduler |
| CI-002 | `tests/real/conftest.py` collection hook 需缩小作用域；普通门禁显式 `--ignore=tests/real` |
| QUALITY-001 | GitHub Ruff 只检查变更 Python 文件，尚无全仓历史清零基线 |
| Real tests 不属于普通门禁 | Quality Gate 不配置真实密钥，也不调用外部模型 |

完整机器可读技术债清单以 `project_state.json` 为准。
