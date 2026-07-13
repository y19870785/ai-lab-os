"""Security utilities —— 安全边界检查。"""
import os
import re
from pathlib import Path

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
SENSITIVE_HEADERS = {"authorization", "x-api-key", "cookie", "set-cookie"}
SENSITIVE_LOG_FIELDS = {"api_key", "password", "secret", "token", "key"}


def check_request_size(data: bytes | str) -> bool:
    """检查请求体大小。"""
    size = len(data) if isinstance(data, bytes) else len(data.encode())
    return size <= MAX_REQUEST_SIZE


def sanitize_log(data: dict) -> dict:
    """脱敏日志中的敏感字段。"""
    result = {}
    for k, v in data.items():
        if any(s in k.lower() for s in SENSITIVE_LOG_FIELDS):
            result[k] = "***REDACTED***"
        elif isinstance(v, dict):
            result[k] = sanitize_log(v)
        else:
            result[k] = v
    return result


def sanitize_error_message(msg: str) -> str:
    """脱敏错误消息，不暴露内部路径和密钥。"""
    # 移除绝对路径
    msg = re.sub(r'[A-Za-z]:\\[^\s]*', '[PATH]', msg)
    msg = re.sub(r'/home/[^\s]*', '[PATH]', msg)
    # 移除 API key 模式
    msg = re.sub(r'sk-[a-zA-Z0-9]{20,}', '***API_KEY***', msg)
    return msg


def validate_file_path(path: str | Path, base_dir: str | Path = ".") -> bool:
    """校验文件路径在允许的 base_dir 内，防止目录遍历。"""
    try:
        resolved = Path(path).resolve()
        base = Path(base_dir).resolve()
        return str(resolved).startswith(str(base))
    except Exception:
        return False


def mask_api_key(key: str) -> str:
    """脱敏 API Key，只显示前后各 4 个字符。"""
    if not key or len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"
