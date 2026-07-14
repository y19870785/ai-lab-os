"""旧 Bootstrap 的兼容包装器。

真实组合逻辑只存在于 :mod:`core.system.factory`。
"""

from __future__ import annotations

import warnings
from dataclasses import replace

from core.system import SystemContainer, create_system, load_system_settings


async def bootstrap(
    config_path: str = "",
    env: str = "",
    enable_api: bool = False,
) -> SystemContainer:
    """Create and start the shared SystemContainer.

    ``config_path`` is retained for call compatibility; configuration now comes
    from ``SystemSettings`` and the process entry point.
    """

    warnings.warn(
        "core.bootstrap.bootstrap is deprecated; use core.system.create_system",
        DeprecationWarning,
        stacklevel=2,
    )
    settings = load_system_settings()
    if env:
        settings = replace(settings, environment=env)
    if enable_api:
        settings = replace(settings, enable_api=True)
    system = await create_system(settings)
    await system.start()
    return system
