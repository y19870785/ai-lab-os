"""配置管理模块。支持层级：默认配置 -> 环境变量 -> 运行时覆盖。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    """数据库连接配置。"""
    host: str = "localhost"
    port: int = 5432
    name: str = "ai_lab"
    user: str = "postgres"
    password: str = ""


class LoggingConfig(BaseModel):
    """日志配置。"""
    level: str = "INFO"
    format: str = "json"
    output: str = "logs/ai-lab.log"


class AppConfig(BaseModel):
    """应用基础配置。"""
    name: str = "AI-Lab"
    version: str = "0.1.0"
    debug: bool = False


class Config(BaseModel):
    """全局配置，包含所有子配置。"""
    app: AppConfig = AppConfig()
    logging: LoggingConfig = LoggingConfig()
    database: DatabaseConfig = DatabaseConfig()

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        """加载配置：先读默认 YAML，再被环境变量覆盖。"""
        load_dotenv()
        cfg = cls()
        if path is None:
            path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                overrides: dict[str, Any] = yaml.safe_load(f) or {}
            cfg = cls(**overrides)
        # 环境变量覆盖
        cfg.app.debug = os.getenv("AI_LAB_DEBUG", str(cfg.app.debug)).lower() == "true"
        cfg.database.host = os.getenv("AI_LAB_DB_HOST", cfg.database.host)
        cfg.database.port = int(os.getenv("AI_LAB_DB_PORT", str(cfg.database.port)))
        cfg.database.name = os.getenv("AI_LAB_DB_NAME", cfg.database.name)
        cfg.database.user = os.getenv("AI_LAB_DB_USER", cfg.database.user)
        cfg.database.password = os.getenv("AI_LAB_DB_PASSWORD", cfg.database.password)
        cfg.logging.level = os.getenv("AI_LAB_LOG_LEVEL", cfg.logging.level)
        return cfg


# 全局单例
config: Config = Config.load()
