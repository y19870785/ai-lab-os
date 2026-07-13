# CEO Assistant
# AI-Lab 第一个真实业务应用
# 超哥的个人工作总控助手

## 使用方法

### CLI

```bash
# 每日简报
python -m cli brief

# 记录工作
python -m cli log "今天和张经理确认了蜂蜡检测方案"

# 创建任务
python -m cli task "提醒我明天下午跟进FDA检测结果"

# 记录决策
python -m cli decide "这次先按21 CFR 175.300做检测"

# 知识问答
python -m cli ask "蜂蜡面包袋FDA检测需要关注什么？"

# 多轮对话
python -m cli chat "你好，帮我看看今天的工作"
```

### REST API

```bash
# 每日简报
curl http://localhost:8000/brief

# 工作记录
curl -X POST http://localhost:8000/work-logs \
  -H "Content-Type: application/json" \
  -d '{"user_input":"今天和张经理确认了蜂蜡检测方案"}'

# 创建任务
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"user_input":"提醒我明天跟进FDA检测结果"}'
```

## 模式

- **Mock 模式**: 未设置 OPENAI_API_KEY 时自动使用
- **Real 模式**: 设置 OPENAI_API_KEY 后使用真实 DeepSeek LLM
