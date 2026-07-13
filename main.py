"""AI-Lab 统一启动入口。

Usage:
    python main.py              # 启动完整服务（API + 全栈）
    python main.py --no-api     # 只启动基础设施，不启动 API
    python main.py --cli chat "Hello"  # CLI 模式
"""

import sys
import os
import asyncio
import signal
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ai-lab.main")

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def main():
    from core.lifecycle import LifecycleManager
    from core.bootstrap import bootstrap

    lm = None
    try:
        lm = await bootstrap(enable_api=True)

        # Keep running until signal
        stop_event = asyncio.Event()

        def _signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down...")
            stop_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        logger.info("AI-Lab running. Press Ctrl+C to stop.")
        await stop_event.wait()

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        if lm:
            await lm.shutdown()
        logger.info("AI-Lab stopped.")


if __name__ == "__main__":
    asyncio.run(main())
