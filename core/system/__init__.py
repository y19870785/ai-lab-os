"""AI-Lab 唯一系统组合入口。"""

from __future__ import annotations

from typing import Any

__all__ = [
    "SystemContainer",
    "SystemSettings",
    "create_system",
    "load_system_settings",
    "make_test_settings",
]


def __getattr__(name: str) -> Any:
    """Resolve public composition objects without eager circular imports."""
    if name == "SystemContainer":
        from core.system.container import SystemContainer
        return SystemContainer
    if name == "create_system":
        from core.system.factory import create_system
        return create_system
    if name in {"SystemSettings", "load_system_settings", "make_test_settings"}:
        from core.system.settings import (
            SystemSettings,
            load_system_settings,
            make_test_settings,
        )
        return {
            "SystemSettings": SystemSettings,
            "load_system_settings": load_system_settings,
            "make_test_settings": make_test_settings,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
