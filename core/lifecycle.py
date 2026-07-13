"""AI-Lab 统一生命周期管理。

定义启动和关闭顺序，确保资源正确初始化和释放。

启动顺序：
    Config → Database → EventBus → Providers → Memory → Knowledge
    → Tools → Agents → Workflow → Scheduler → Task → Coordination → Applications → API

关闭时反向执行。
"""

from __future__ import annotations
import asyncio
import logging
import signal
from typing import Any

logger = logging.getLogger("ai-lab.lifecycle")


class LifecycleManager:
    """统一生命周期管理器。

    管理所有 AI-Lab 子系统的初始化和关闭。
    """

    def __init__(self):
        self._components: list[tuple[str, Any, Any, Any]] = []
        # (name, instance, init_fn, shutdown_fn)

    def register(self, name: str, instance: Any,
                 init_fn, shutdown_fn) -> None:
        """注册一个需要生命周期管理的组件。

        Args:
            name: 组件名称（用于日志）
            instance: 组件实例
            init_fn: async callable(instance) -> None
            shutdown_fn: async callable(instance) -> None
        """
        self._components.append((name, instance, init_fn, shutdown_fn))

    async def startup(self) -> None:
        """按注册顺序启动所有组件。"""
        logger.info("=" * 50)
        logger.info("AI-Lab starting up...")
        logger.info("=" * 50)
        for name, instance, init_fn, _ in self._components:
            logger.info(f"  [START] {name}...")
            try:
                if init_fn:
                    await init_fn(instance)
                logger.info(f"  [OK]    {name}")
            except Exception as e:
                logger.error(f"  [FAIL]  {name}: {e}")
                raise

    async def shutdown(self) -> None:
        """按注册顺序反向关闭所有组件。"""
        logger.info("=" * 50)
        logger.info("AI-Lab shutting down...")
        logger.info("=" * 50)
        for name, instance, _, shutdown_fn in reversed(self._components):
            logger.info(f"  [STOP]  {name}...")
            try:
                if shutdown_fn:
                    await shutdown_fn(instance)
                logger.info(f"  [OK]    {name}")
            except Exception as e:
                logger.error(f"  [WARN]  {name}: {e}")

    async def health_check(self) -> dict[str, Any]:
        """检查所有组件健康状态。"""
        status = {"healthy": True, "components": {}}
        for name, instance, _, _ in self._components:
            try:
                if hasattr(instance, "health_check"):
                    hc = await instance.health_check()
                elif hasattr(instance, "is_available"):
                    hc = {"ready": instance.is_available()}
                else:
                    hc = {"ready": True}
                status["components"][name] = hc
            except Exception as e:
                status["components"][name] = {"error": str(e)}
                status["healthy"] = False
        return status

    @property
    def component_count(self) -> int:
        return len(self._components)
