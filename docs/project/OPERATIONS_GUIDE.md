# Operations Guide —— v0.30.0 Alpha

## 启动
```bash
# CLI
python -m cli health
python -m cli chat "Hello"

# API
python -m api.app
# OpenAPI docs: http://localhost:8000/docs

# Docker
docker compose -f deploy/docker-compose.yml up -d
```

## 关闭顺序

API → Application → Coordination → Task → Scheduler → Workflow → Agent → Tool → Knowledge → Memory → Provider → EventBus → Database

## 监控

- GET /health — 健康检查
- 日志输出至 logs/ 目录
- trace_id 贯穿全链路
