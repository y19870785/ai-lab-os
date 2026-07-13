# Deployment Guide —— v0.31.0

## Windows 本地启动

```bash
# 1. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置
cp .env.example .env
# 编辑 .env，可选填入 OPENAI_API_KEY

# 4. 启动
python -m cli health
python -m cli chat "Hello"
python -m api.app  # 启动 REST API
```

## Docker Compose

```bash
docker compose -f deploy/docker-compose.yml build
docker compose -f deploy/docker-compose.yml up -d
curl http://localhost:8000/health
docker compose -f deploy/docker-compose.yml down
```

## 配置说明

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| OPENAI_API_KEY | OpenAI API Key（留空使用 Mock） | (空) |
| OPENAI_MODEL | LLM 模型 | gpt-4o-mini |
| OPENAI_EMBEDDING_MODEL | Embedding 模型 | text-embedding-3-small |
| CHROMA_PERSIST_DIR | Chroma 数据目录 | data/chroma |

## 数据目录

- `data/sqlite/` — SQLite 数据库
- `data/chroma/` — Chroma 向量数据
- `logs/` — 运行日志

## 常见问题

**Q: 启动显示 MOCK MODE？**
A: 未设置 OPENAI_API_KEY，系统自动降级到 Mock。设置 `.env` 中的 API Key 后切换。

**Q: 如何切换 Provider？**
A: 编辑 `config/alpha.yaml` 中的 `providers.llm.default`。

**Q: Docker 无法启动？**
A: 检查 Docker Desktop 是否运行，端口 8000 是否被占用。
