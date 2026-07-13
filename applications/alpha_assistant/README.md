# Alpha Assistant

AI-Lab 首个可运行业务应用。

## 运行方式

### CLI
```bash
python -m cli chat "Hello, what can you do?"
```

### REST API
```bash
python -m api.app
# Then: curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"user_input":"Hello"}'
```

## 模式

- **Mock 模式**（默认）：无 API Key 时自动使用，带 `[MOCK MODE]` 标记
- **Real 模式**：设置 `OPENAI_API_KEY` 环境变量后自动切换
