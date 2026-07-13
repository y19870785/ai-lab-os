"""CEO Assistant CLI —— 知识问答命令。"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

async def run(args):
    """知识问答。"""
    user_input = " ".join(args) if args else ""
    if not user_input:
        print("Usage: python -m cli ask <问题>")
        print("Example: python -m cli ask \"蜂蜡面包袋FDA检测需要关注什么？\"")
        return

    from core.lifecycle import LifecycleManager
    from core.bootstrap import bootstrap

    lm = None
    try:
        lm = await bootstrap()
        
        from applications.models import ApplicationRequest
        req = ApplicationRequest(application_name="ceo-assistant", user_input=user_input)
        
        from api.dependencies import get_runtime
        runtime = get_runtime()
        resp = await runtime.execute(req)

        mode = "REAL" if os.getenv("OPENAI_API_KEY") else "MOCK"
        print(f"\n[CEO Assistant | {mode}]")
        print(resp.answer)
        if resp.citations:
            print(f"\n引用来源: {', '.join(resp.citations)}")

    finally:
        if lm:
            await lm.shutdown()
