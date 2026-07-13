# AI-Lab Model Policy

> 模型管理规范。定义模型的抽象原则、Provider 接口、本地/云端策略和成本控制。

---

## 1. 核心原则：模型不可知

**业务层禁止直接绑定具体模型。**

```
  正确：                    错误：
  ┌──────────┐              ┌──────────┐
  │  Agent   │              │  Agent   │
  └────┬─────┘              └────┬─────┘
       │ uses                    │ calls
       ▼                         ▼
  ┌──────────┐              ┌──────────┐
  │  Model   │              │ GPT-4o   │
  │  Facade  │              │ (hardcode)
  └────┬─────┘              └──────────┘
       │ routes
       ▼
  ┌──────────┬──────────┐
  │ GPT-4o  │ Claude  │ Ollama  │
  └──────────┴──────────┘
```

所有层（Agent / Knowledge / Memory）通过 `ModelFacade` 接口调用模型，不直接实例化任何 provider 的客户端。

## 2. Provider 接口原则

### 接口定义

```python
class ModelProvider(ABC):
    """模型 Provider 抽象。所有模型接入点必须实现此接口。"""

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], config: ChatConfig) -> ChatResponse: ...
    @abstractmethod
    async def chat_stream(self, messages: list[ChatMessage], config: ChatConfig) -> AsyncIterator[ChatChunk]: ...
    @property
    @abstractmethod
    def model_name(self) -> str: ...
    @property
    @abstractmethod
    def provider_name(self) -> str: ...
```

### 设计约束

| 约束 | 说明 |
| --- | --- |
| 统一接口 | 所有 Provider 实现同一个 `ModelProvider` 接口 |
| 可切换 | 运行时通过配置切换 Provider，无需改代码 |
| 降级 | 主 Provider 不可用时自动降级到备用 Provider |
| 可观测 | 每次调用记录 model / tokens / latency / cost |
| 隔离 | 每个 Provider 的配置和凭证各自管理，互不干扰 |

## 3. 本地模型策略

| 策略 | 说明 |
| --- | --- |
| 优先使用 | 当满足质量和性能要求时，优先选择本地模型 |
| 接口 | 通过 Ollama / llama.cpp 等本地推理引擎暴露兼容 API |
| 模型缓存 | 本地模型文件按版本缓存，避免重复下载 |
| 降级 | 本地模型不可用时（如 GPU 内存不足），降级到云端模型 |

### 适用场景

| 场景 | 推荐策略 | 理由 |
| --- | --- | --- |
| 简单文本分类/实体提取 | 本地小模型（3B-8B） | 速度快、成本低 |
| 通用对话/助手 | 本地中模型（8B-30B） | 隐私优先 |
| 复杂推理/代码生成 | 云端模型（GPT-4o / Claude） | 质量优先 |
| 知识向量化 | 本地 embedding 模型 | 高频调用，云端成本高 |

## 4. 云端模型策略

| 策略 | 说明 |
| --- | --- |
| 按需使用 | 仅在本地模型无法满足需求时使用云端模型 |
| API Key 隔离 | 每个 Provider 的 API Key 通过环境变量管理，不出现在代码中 |
| 限流保护 | 云端调用必须配置 rate limit 和 retry，防止超预算 |
| 失败降级 | 云端不可用时（网络/限流/配额），自动降级到本地模型 |

### 使用条件

使用云端模型前必须满足以下条件之一：
1. 当前任务在本地模型上的表现低于质量阈值
2. 当前任务需要特定的云端模型独占能力（如多模态）
3. 本地模型资源不足（GPU 显存不够）

## 5. 模型切换规则

### 自动切换（Runtime）

```
请求发送到 ModelFacade
    │
    ▼
[路由策略]：
    │  按 task_type 路由到默认 provider
    │  按配置中的 model_priority 列表
    ▼
尝试 Provider 1（如 GPT-4o）
    │  ✅ 成功 → 返回
    │  ❌ 失败（超时/限流/错误）
    ▼
尝试 Provider 2（如 Claude）
    │  ✅ 成功 → 返回
    │  ❌ 失败
    ▼
尝试 Provider 3（如本地 Ollama）
    │  ✅ 成功 → 返回
    │  ❌ 失败 → 抛出 ModelUnavailableError
```

### Provider 优先级配置

```yaml
model:
  default_provider: "openai"
  routing:
    chat:
      priority: ["openai", "anthropic", "ollama"]
      fallback_strategy: "next_available"
    embedding:
      priority: ["ollama", "openai"]
      fallback_strategy: "next_available"
```

## 6. 成本控制原则

### 预算管理

| 规则 | 说明 |
| --- | --- |
| 月度预算 | 云端模型设置月度 token 预算上限 |
| 调用配额 | 每种 model_type 设置每小时调用配额 |
| 成本告警 | 达到预算的 80% 时发送告警，100% 时自动切换降级 |
| 使用报告 | 每周生成模型使用和成本报告 |

### Token 追踪

```python
class ModelUsage(BaseModel):
    """模型调用记录。记录每次调用的 token 消耗和成本。"""
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int = 0
    cost: float = 0.0
    latency_ms: int
    timestamp: datetime
```

### 成本优化建议

- 高频调用的 embedding 任务使用本地模型
- 长上下文任务在本地模型和云端模型之间做成本-质量对比
- 缓存重复的模型调用结果（TTL 相同的查询返回缓存的 embedding）
- 批量处理短文本，减少 API 调用次数

## 7. Model Facade 实现规划

```
core/model/
├── __init__.py          # 导出 ModelFacade
├── facade.py            # ModelFacade 统一入口（路由/降级/追踪）
├── protocol.py          # ModelProvider 抽象接口
├── config.py            # 模型配置（provider 列表、优先级、配额）
├── usage.py             # Token/cost 追踪和预算管理
└── providers/
    ├── __init__.py
    ├── openai.py         # OpenAI / Azure OpenAI Provider
    ├── anthropic.py      # Anthropic Claude Provider
    └── ollama.py         # 本地 Ollama Provider
```

> 注：`core/model/` 当前为架构设计阶段，Phase 2.x 实现。

---

> 最后更新：2026-07-12 | 维护者：Lin Yuyan
