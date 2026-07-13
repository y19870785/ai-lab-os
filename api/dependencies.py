"""API Dependencies —— 单例管理。"""
from applications.runtime import ApplicationRuntime
from applications.registry import ApplicationRegistry

_runtime: ApplicationRuntime | None = None

def get_runtime() -> ApplicationRuntime:
    global _runtime
    if _runtime is None:
        _runtime = ApplicationRuntime(registry=ApplicationRegistry())
    return _runtime
