"""AI-Lab 唯一系统组合入口。"""

from core.system.container import SystemContainer
from core.system.factory import create_system
from core.system.settings import SystemSettings, load_system_settings, make_test_settings

__all__ = [
    "SystemContainer",
    "SystemSettings",
    "create_system",
    "load_system_settings",
    "make_test_settings",
]
