"""结构化日志模块。

支持控制台和文件输出，JSON 格式。
所有日志自动附带 Trace ID 等分布式上下文。

使用方式：
    from core.logging import get_logger, LogContext

    logger = get_logger("core.bus")

    # 在上下文中记录
    with LogContext(trace_id="abc123", agent_id="analyst"):
        logger.info("event.published", extra={"event_id": "evt_001"})

    # 输出：
    # {
    #   "timestamp": "...",
    #   "level": "INFO",
    #   "logger": "core.bus",
    #   "message": "event.published",
    #   "trace_id": "abc123",
    #   "agent_id": "analyst",
    #   "event_id": "evt_001"
    # }
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── 上下文管理 ──

_context = threading.local()
_context.trace_id: str | None = None
_context.agent_id: str | None = None
_context.session_id: str | None = None


class LogContext:
    """日志上下文管理器。

    在 with 块内设置上下文字段，所有日志自动附带。
    支持嵌套——推出 with 块后恢复上一级上下文。

    用法：
        with LogContext(trace_id="abc", agent_id="analyst"):
            logger.info("hello")
    """

    def __init__(
        self,
        trace_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._trace_id = trace_id
        self._agent_id = agent_id
        self._session_id = session_id
        self._extra = kwargs
        self._snapshot: dict[str, Any] | None = None

    def __enter__(self) -> LogContext:
        self._snapshot = {
            "trace_id": getattr(_context, "trace_id", None),
            "agent_id": getattr(_context, "agent_id", None),
            "session_id": getattr(_context, "session_id", None),
        }
        if self._trace_id is not None:
            _context.trace_id = self._trace_id
        if self._agent_id is not None:
            _context.agent_id = self._agent_id
        if self._session_id is not None:
            _context.session_id = self._session_id
        return self

    def __exit__(self, *args: Any) -> None:
        if self._snapshot:
            _context.trace_id = self._snapshot["trace_id"]
            _context.agent_id = self._snapshot["agent_id"]
            _context.session_id = self._snapshot["session_id"]


def get_current_trace_id() -> str | None:
    """获取当前线程的 trace_id。"""
    return getattr(_context, "trace_id", None)


def set_current_trace_id(trace_id: str) -> None:
    """设置当前线程的 trace_id。"""
    _context.trace_id = trace_id


# ── 日志格式化器 ──

class JsonFormatter(logging.Formatter):
    """JSON 格式日志格式化器。

    自动注入：
    - timestamp: 当前时间
    - trace_id: 从 LogContext 获取
    - agent_id: 从 LogContext 获取
    - session_id: 从 LogContext 获取
    - extra 中的字段直接展开到顶层
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 注入 LogContext 字段
        trace_id = getattr(_context, "trace_id", None)
        if trace_id:
            log_entry["trace_id"] = trace_id

        agent_id = getattr(_context, "agent_id", None)
        if agent_id:
            log_entry["agent_id"] = agent_id

        session_id = getattr(_context, "session_id", None)
        if session_id:
            log_entry["session_id"] = session_id

        # 注入 extra 字段
        if record.args:
            # 支持 logger.info("msg", extra={...}) 中的 extra
            extra = record.args[0] if isinstance(record.args, dict) else {}
            # 实际通过 extra 参数传入的字段在 __dict__ 中
            for key, value in record.__dict__.items():
                if key not in (
                    "args", "asctime", "created", "exc_info", "exc_text",
                    "filename", "funcName", "levelname", "levelno",
                    "lineno", "module", "msecs", "message", "msg",
                    "name", "pathname", "process", "processName",
                    "relativeCreated", "stack_info", "thread", "threadName",
                ):
                    log_entry[key] = value

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


# ── 初始化 ──

_log_initialized = False


def setup_logging(
    level: str = "INFO",
    log_file: str | None = "logs/ai-lab.log",
) -> None:
    """初始化日志系统。

    设置根 logger：
    - 控制台输出（JSON 格式）
    - 文件输出（JSON 格式，可选）

    Args:
        level: 日志级别
        log_file: 日志文件路径。None = 不输出到文件。
    """
    global _log_initialized
    if _log_initialized:
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 控制台
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(JsonFormatter())
    root.addHandler(console)

    # 文件
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        root.addHandler(fh)

    _log_initialized = True


def get_logger(name: str) -> logging.Logger:
    """获取命名 logger。"""
    return logging.getLogger(name)
