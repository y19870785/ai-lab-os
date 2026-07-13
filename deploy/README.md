# Docker 部署指南

## 构建
```bash
docker build -t ai-lab:alpha -f deploy/Dockerfile .
```

## 启动
```bash
# 复制 .env
cp .env.example .env
# 编辑 .env 填入 API Key（可选）

docker compose -f deploy/docker-compose.yml up -d
```

## 验证
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"user_input":"Hello"}'
```

## 停止
```bash
docker compose -f deploy/docker-compose.yml down
```
