"""Provider Benchmark —— 测量 Provider 性能（Mock 环境）。"""

import asyncio
import time
import sys
sys.path.insert(0, ".")

from core.providers.llm.mock import MockLLMProvider
from core.providers.llm.protocol import LLMRequest, Message


async def benchmark_llm_generate(n: int = 100):
    llm = MockLLMProvider()
    await llm.initialize()
    t0 = time.time()
    for i in range(n):
        req = LLMRequest(messages=[Message(role="user", content=f"Test {i}")])
        await llm.generate(req)
    elapsed = time.time() - t0
    print(f"  LLM generate x{n}: {elapsed:.2f}s ({n/elapsed:.0f} req/s)")
    await llm.shutdown()


async def benchmark_llm_stream(n: int = 50):
    llm = MockLLMProvider()
    await llm.initialize()
    t0 = time.time()
    for i in range(n):
        req = LLMRequest(messages=[Message(role="user", content=f"Stream {i}")])
        async for _ in llm.stream(req):
            pass
    elapsed = time.time() - t0
    print(f"  LLM stream  x{n}: {elapsed:.2f}s ({n/elapsed:.0f} req/s)")
    await llm.shutdown()


async def main():
    print("=" * 60)
    print("Provider Layer Benchmark (Mock)")
    print("=" * 60)
    await benchmark_llm_generate(100)
    await benchmark_llm_stream(50)


if __name__ == "__main__":
    asyncio.run(main())
