# AI-Lab Current Risks —— 技术债与风险摘要

> 冻结版本：v0.32.4 | 日期：2026-07-14

## P0：阻塞发布

（当前无 P0 级别阻塞项，因为项目尚未进入生产发布阶段）

---

## P1：下一迭代必须处理

| 编号 | 问题 | 影响模块 | 说明 |
|---|---|---|---|
| P1-1 | API 无鉴权、CORS `*` | API | 本地绑定 127.0.0.1 暂时安全，但部署到网络后是严重安全漏洞 |
| P1-2 | Real Provider 测试不可靠 | tests/real/ | 机器 SOCKS 代理导致 openai SDK 初始化失败，需要配置 fallback 或跳过机制 |
| P1-3 | Docker 未经真实验证 | deploy/ | Dockerfile 和 compose 配置存在但从未实际 docker build + run |
| P1-4 | Chroma 生命周期管理脆弱 | Knowledge | Chroma 客户端初始化/关闭异常时可能泄漏连接 |
| P1-5 | start.bat 依赖清除代理 | scripts/ | 如果用户机器有系统级 SOCKS 代理，不清除会导致 LLM 初始化失败 |
| P1-6 | Prompt 注入无防护 | CEO Assistant | 用户输入直接拼入 system prompt，无任何注入检测 |

---

## P2：中期风险

| 编号 | 问题 | 说明 |
|---|---|---|
| P2-1 | SQLite 高并发无连接池保护 | 多 Agent 并发时可能出现 database locked |
| P2-2 | Intent Router 误判率高 | 纯规则匹配，"完成了"、"怎么" 等词多次误匹配 |
| P2-3 | Knowledge 来源可信度未标记 | 所有知识同等对待，无置信度/来源可信度区分 |
| P2-4 | Daily Brief 数据真实性未验证 | Brief 可能引用过期或错误数据 |
| P2-5 | Workspace 隔离仅文件级别 | 无加密，无法防止跨 Workspace 数据泄露 |
| P2-6 | TD-001 测试辅助函数 id=None 问题 | 部分测试代码存在 Pydantic default_factory 不触发问题 |
| P2-7 | RFC/ADR 编号重复 | RFC-013 和 ADR-024/025 各有两篇，编号冲突 |
| P2-8 | 部分模块文档与代码版本不一致 | ARCHITECTURE 版本表停在不一致的位置 |

---

## P3：优化建议

| 编号 | 问题 | 说明 |
|---|---|---|
| P3-1 | asyncio 生命周期不统一 | 部分模块用 async with，部分用 initialize/shutdown |
| P3-2 | Provider 降级语义未定义 | 当 LLM Provider 失败时，应降级到 Mock 还是报错？未明确定义 |
| P3-3 | 过度架构风险 | 十层架构中可能有 2-3 层是为了"完整性"而非"业务需要" |
| P3-4 | 公共 API 存在重复 | ApplicationRuntime.execute + CEOAssistant.run 功能重叠 |
| P3-5 | 文档与代码偏差 | CHANGELOG 和 ARCHITECTURE 的版本记录有滞后 |

---

## 文档与代码不一致项

| 项 | 说明 |
|---|---|
| ARCHITECTURE.md 版本表 | 缺少 v0.32.0~v0.32.4 的完整记录 |
| README.md | 测试统计数据可能已过期 |
| CHANGELOG.md | 较早版本的详细内容为乱码（编码问题） |

---

## 环境依赖风险

- Windows 10/11 编码工具链不稳定（PowerShell/CMD 中文管道乱码）
- httpx 0.28.1 + SOCKS 代理兼容性（需要 pip install httpx[socks]）
- Python 3.10.9（未来可能需升级到 3.12+）
