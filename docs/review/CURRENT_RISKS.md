# AI-Lab Current Risks — 技术债与风险摘要

> 当前源码版本：v0.34.0 Alpha | 更新日期：2026-07-22

## 当前质量与发布事实

- GitHub Quality Gate 使用 Python 3.12，在 Pull Request、main push 与 `workflow_dispatch` 上运行。
- 当前正式 Quality Gate 基线为 run `29884309247`：Ruff `SUCCESS`，non-real pytest `1163 passed, 6 skipped, 27 warnings`。
- pytest 正式门禁继续显式排除 `tests/real`；real Provider 测试需要独立授权的凭据与网络条件，skip 不代表通过。
- v0.34.0 已通过 GitHub Tag 和 GitHub Release 作为 Alpha Pre-release 发布。
- Ruff 只检查本次 PR 或 push 变更的 Python 文件，不代表全库历史 Ruff 债务已清零。

## P0：阻塞发布

当前无新增 P0。

## P1：下一阶段应处理

| 编号 | 问题 | 影响 | 当前事实 |
|---|---|---|---|
| QUALITY-001 | 全库 Ruff 历史基线尚未建立 | 代码质量 | 当前 CI 仅对变更 Python 文件做增量检查 |
| AGENDA-001 | Daily Agenda 来源组装不是可选聚合 | Agenda 可用性 | Reminder/Scheduler 未启用时会影响整体 Agenda；应让各来源按能力独立参与 |
| SCHEDULER-001 | Scheduler 时序测试与持续运行基线不足 | 调度可靠性 | 已观察到终态前短暂 `running` 的时序波动，仍需独立稳定化 |
| DEPLOY-001 | Docker 未经完整真实验证 | 部署 | Dockerfile 与 compose 存在，但缺少受控 build/run、持久化卷、关闭与恢复验收 |
| SECURITY-001 | 静态单一 Bearer Token | API | 无用户身份、OAuth/JWT、RBAC；token 热轮换未实现 |
| KNOWLEDGE-001 | Knowledge 主链路尚未闭环 | Knowledge | reindex、chunk persistence、citation 与真实产品主链路未完成 |
| P1-PROMPT | Prompt 注入防护不足 | CEO Assistant | 仍需持续明确输入信任边界与工具调用防护 |

## P2：中期风险

| 编号 | 问题 | 说明 |
|---|---|---|
| P2-1 | SQLite 并发能力有限 | 多执行单元并发时仍可能发生锁竞争；当前不是分布式存储 |
| P2-2 | 意图路由仍以确定性规则为主 | 已有读写安全边界，但边缘自然语言仍需要持续回归覆盖 |
| P2-3 | Knowledge 来源可信度未分级 | 缺少完整的来源可信度与时效性策略 |
| P2-4 | Workspace 不是强租户隔离 | 现有 workspace 边界不等于用户身份、加密或强多租户安全 |
| P2-5 | Real Provider 验证依赖外部条件 | 必须由明确授权的密钥、网络与测试任务单独执行 |
| P2-6 | Reminder 外部通知未实现 | 当前持久化与查询状态不代表外部通知已送达 |

## P3：架构与运维观察项

| 编号 | 问题 | 说明 |
|---|---|---|
| P3-1 | 生命周期接口尚未完全统一 | 部分模块使用 context manager，部分使用 initialize/shutdown |
| P3-2 | Provider 降级策略需要继续明确 | Mock、失败返回与真实 Provider 故障边界应保持显式 |
| P3-3 | 分层架构存在复杂度成本 | 后续新增抽象必须由真实业务压力证明 |
| P3-4 | 部分应用入口职责相近 | ApplicationRuntime 与 CEO Assistant 的边界需要持续保持清晰 |
| P3-5 | Windows 编码与脚本兼容性 | PowerShell/CMD 中文管道仍需保留平台回归测试 |

## 已解决

- CI-002：`tests/real/conftest.py` 的 collection skip 已按规范化路径限定于 `tests/real/**`；混合收集时普通测试正常执行，real 测试在无凭据时明确 skip。
- “API 无鉴权”：Bearer Token Authentication 已存在并默认启用。
- “CORS `*`”：当前为显式 allowlist 与默认 deny-all，鉴权开启时拒绝通配符。

安全风险并未因此全部消失；当前真实限制仍包括静态单 token、无用户身份/RBAC、无法热轮换，以及缺少强多租户隔离。
