# ADR-001: Core Layer 包结构

## Metadata

| Field        | Value                                |
| ------------ | ------------------------------------ |
| **ADR 编号** | 001                                  |
| **标题**     | Core Layer 包结构                     |
| **状态**     | 已接受                                |
| **作者**     | Lin Yuyan                            |
| **创建日期** | 2026-07-12                           |
| **更新日期** | 2026-07-12                           |
| **关联 RFC** | RFC-001                              |
| **取代**     | —                                    |

## 1. 背景

Core Layer 是 AI-Lab 的基础设施层，需要容纳多个子模块（Config、Logging、Message Bus、Data Access、Agent Runtime、Identity）。需要确定包结构方案，使模块职责清晰、导入关系可管理。

## 2. 决策

采用**按职责拆分子包**的方案：

```
core/
├── __init__.py       # 版本号、全局单例导出
├── config.py         # Config Manager
├── logging.py        # Logging System
├── bus/              # Message Bus 子系统
│   ├── __init__.py
│   ├── protocol.py   # 抽象接口
│   ├── event.py      # 数据模型
│   └── memory.py     # 内存实现
├── data/             # Data Access Layer
│   ├── __init__.py
│   ├── protocol.py
│   ├── repository.py
│   ├── cache.py
│   └── client.py
├── agent/            # Agent Runtime
│   ├── __init__.py
│   ├── protocol.py
│   ├── models.py
│   └── runtime.py
└── identity/         # Identity & Session
    ├── __init__.py
    ├── protocol.py
    ├── models.py
    └── manager.py
```

## 3. 后果

### 正面

- 每个子包有明确的职责边界
- 避免单个 `core/` 目录下文件过多
- 子包间通过 `protocol.py`（抽象接口）解耦
- 方便未来子模块独立提取为独立包

### 负面

- 比单层结构多一层嵌套，导入路径略长（`from core.bus import ...`）
- 对初学者来说需要理解子包划分逻辑

### 风险

- 如果子模块间的 "protocol" 定义在多个文件中分散，可能导致循环导入

**缓解方案**：每个子包的 `protocol.py` 只导入数据模型（`event.py` / `models.py`），不导入实现类。实现类依赖接口，接口不依赖实现。

## 4. 理由

选择了按职责拆分子包，而不是"所有 ABC 放一个 `core/abc.py`"或"所有模型放一个 `core/models.py`"，原因：

1. **内聚性**：每个模块的接口、模型、实现放在一起，修改时只需关注一个子包
2. **可发现性**：新开发者看到 `core/bus/` 就知道"这里是消息系统"
3. **可测试性**：每个子包可以独立 mock 测试
4. **渐进式**：当前只需要其中几个子包，其余可以留空先不实现

## 5. 相关链接

- [RFC-001: Core Layer Architecture](docs/rfc/001-core-layer-architecture.md)
- [DEVELOPMENT_GUIDE.md](docs/guides/DEVELOPMENT_GUIDE.md)
