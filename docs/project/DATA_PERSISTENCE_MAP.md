# AI-Lab Data Persistence Map —— 数据持久化地图

> 冻结版本：v0.32.4 | 日期：2026-07-14

## 持久化数据文件

| 路径 | 内容 | 持久化 | 可恢复 | 状态 |
|---|---|---|---|---|
| `data/sqlite/episodic.db` | 工作记录（Episodic Memory） | ✅ | ✅ | 已验证 |
| `data/sqlite/semantic.db` | 语义记忆 | ✅ | ✅ | 已验证 |
| `data/sqlite/decision.db` | 决策记录 | ✅ | ✅ | 已验证 |
| `data/sqlite/demo_episodic.db` | Demo 数据 | ✅ | ❌ | 演示用 |
| `data/chroma/chroma.sqlite3` | Chroma 元数据 | ✅ | ✅ | 已验证 |
| `data/chroma/<uuid>/` | Chroma 向量数据 (HNSW) | ✅ | ✅ | 已验证 |

## 仅内存（不持久化）

| 数据 | 存储位置 | 说明 |
|---|---|---|
| Session Memory | `SessionMemory`（内存 dict） | 有 TTL，重启丢失 |
| EventBus 事件队列 | `asyncio.Queue`（内存） | 重启丢失 |
| Agent Context | `ApplicationContext`（内存） | 随会话生命周期 |
| Provider Cache | `ProviderCache`（内存） | TTL 过期清除 |

## 持久化但不可直接恢复

| 数据 | 说明 |
|---|---|
| Workflow Checkpoint | 接口已设计，未实现 SQLite 持久化 |
| Task Checkpoint | 同上 |
| Scheduler Job State | SQLite 持久化（`core/scheduler/persistence.py`），恢复接口存在但未经 Long-running 验证 |

## 配置与日志

| 路径 | 说明 |
|---|---|
| `.env` | API Key、模型、数据库路径配置 |
| `config/default.yaml` | 默认 YAML 配置 |
| `config/alpha.yaml` | Alpha 环境配置 |
| `config/development.yaml` | 开发环境配置 |
| `logs/` | 运行日志目录 |

## 备份与恢复现状

- 无自动备份机制
- `DatabaseManager.backup()` / `restore()` 接口已定义，未实现
- 手动备份：复制 `data/` 目录即可恢复所有数据
- Chroma 数据：复制 `data/chroma/` 目录
- 无需恢复的数据：Session Memory、EventBus 状态、Provider Cache
