# AI-Lab Known Limitations

> 冻结版本：v0.32.4 | 日期：2026-07-14

## 功能限制

| 限制 | 说明 | 影响 |
|---|---|---|
| 无多用户/多租户 | 所有数据属于单一用户，无用户隔离 | 无法共享给团队使用 |
| 无 API 鉴权 | CORS `*`，无 token/OAuth | 仅限本地使用 |
| 仅本地存储 | SQLite + Chroma，无云存储后端 | 数据不可跨设备同步 |
| 无分布式 | 单进程运行，无消息队列/分布式锁 | 性能有上限 |

## 稳定性限制

| 限制 | 说明 |
|---|---|
| Long-running 未验证 | 未测试 >30 分钟的连续运行 |
| Real Provider 测试不可靠 | 依赖本地环境变量 + 无 SOCKS 代理 |
| Docker 未实测 | Dockerfile/compose 存在但未经 build + run |
| Windows 编码不稳定 | PowerShell/CMD 管道传输中文可能乱码 |

## 安全限制

| 限制 | 说明 |
|---|---|
| API Key 明文存储 | `.env` 文件包含明文 Key |
| Prompt 注入无防护 | 用户输入直接拼入 system prompt |
| 无 HTTPS | 仅本地 HTTP |
| 无审计日志持久化 | 审计记录仅内存 |

## 质量限制

| 限制 | 说明 |
|---|---|
| Intent Router 误判率高 | 纯规则匹配，约 10-15% 误判率 |
| Knowledge 可信度未标记 | 所有知识同等对待 |
| Daily Brief 数据可能过时 | 无时间窗口验证 |
| RFC/ADR 编号重复 | RFC-013 + ADR-024/025 编号冲突 |
| 部分文档滞后于代码 | ARCHITECTURE/README 版本记录有缺失 |
