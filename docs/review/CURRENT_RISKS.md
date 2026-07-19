# AI-Lab Current Risks — 技术债与风险摘要

> 当前版本：`0.33.0` | main：`23b54be4bd3030c564c2e1a0325eaf36199357fe` | 对账日期：2026-07-19

## 当前质量与安全边界

- GitHub Quality Gate 使用 Python 3.12，在 Pull Request、main push 与 `workflow_dispatch` 上运行。
- pytest 门禁显式排除 `tests/real`；Ubuntu 当前基线为 `1096 passed, 6 skipped, 27 warnings`。
- Ruff 只检查本次 PR 或 push 变更的 Python 文件，不代表全库历史 Ruff 债务已清零。
- API 已实现 Bearer Token Authentication，默认启用；缺少必要 token 配置时启动失败。
- CORS 使用显式 allowlist，默认不允许跨域；启用鉴权时拒绝通配符 `*`。

## P0：阻塞发布

当前无新增 P0。项目仍为 `0.33.0`，SP-004～SP-013B 是尚未形成新 Tag 或 Release 的后续 main 工作。

## P1：下一阶段应处理

| 编号 | 问题 | 影响 | 当前事实 |
|---|---|---|---|
| CI-002 | `tests/real/conftest.py` collection hook 作用域过宽 | CI / 测试收集 | 普通门禁通过 `--ignore=tests/real` 明确规避；不得据此声称 real 测试通过 |
| QUALITY-001 | 全库 Ruff 历史基线尚未建立 | 代码质量 | 当前 CI 仅对变更 Python 文件做增量检查 |
| P1-SEC-1 | 静态单一 Bearer Token | API | 无用户身份、OAuth/JWT、RBAC；token 轮换需要重启 |
| P1-3 | Docker 未经完整真实验证 | deploy/ | Dockerfile 与 compose 存在，但缺少受控 build + run 验证记录 |
| P1-4 | Chroma 生命周期管理脆弱 | Knowledge | 初始化或关闭异常时仍有资源生命周期风险 |
| P1-6 | Prompt 注入防护不足 | CEO Assistant | 仍需明确输入信任边界与工具调用防护 |

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
| P3-3 | 十一层架构存在复杂度成本 | Coordination 已是独立层；后续新增抽象必须由真实业务压力证明 |
| P3-4 | 部分应用入口职责相近 | ApplicationRuntime 与 CEO Assistant 的边界需要持续保持清晰 |
| P3-5 | Windows 编码与脚本兼容性 | PowerShell/CMD 中文管道仍需保留平台回归测试 |

## 已关闭的旧风险结论

以下旧描述已经被 SP-006 及当前代码推翻，不再是当前风险：

- “API 无鉴权”：Bearer Token Authentication 已存在并默认启用。
- “CORS `*`”：当前为显式 allowlist 与默认 deny-all，鉴权开启时拒绝通配符。

安全风险并未因此全部消失；当前真实限制是静态单 token、无用户身份/RBAC、轮换需重启，以及缺少强多租户隔离。
