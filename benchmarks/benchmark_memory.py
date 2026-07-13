"""Memory Benchmark —— 测量 Memory Layer 吞吐量。"""

import asyncio
import time
import sys
sys.path.insert(0, ".")

from core.memory.manager import MemoryManager
from core.memory.models import MemoryType, MemoryItem


async def benchmark_save(n: int = 1000):
    mgr = MemoryManager()
    t0 = time.time()
    for i in range(n):
        item = MemoryItem(
            content=f"Benchmark memory entry {i}",
            memory_type=MemoryType.EPISODIC,
            metadata={"bench": True, "index": i},
        )
        mgr.save(item)
    elapsed = time.time() - t0
    print(f"  save x{n}: {elapsed:.2f}s ({n/elapsed:.0f} ops/s)")
    return elapsed


async def benchmark_retrieve(n: int = 500):
    mgr = MemoryManager()
    # Pre-populate
    ids = []
    for i in range(n):
        item = MemoryItem(
            content=f"Retrieve test {i}",
            memory_type=MemoryType.EPISODIC,
        )
        mgr.save(item)
        ids.append(item.id)

    t0 = time.time()
    for mid in ids:
        mgr.retrieve(mid)
    elapsed = time.time() - t0
    print(f"  retrieve x{n}: {elapsed:.2f}s ({n/elapsed:.0f} ops/s)")
    return elapsed


async def benchmark_delete(n: int = 500):
    mgr = MemoryManager()
    ids = []
    for i in range(n):
        item = MemoryItem(content=f"Delete test {i}", memory_type=MemoryType.EPISODIC)
        mgr.save(item)
        ids.append(item.id)

    t0 = time.time()
    for mid in ids:
        mgr.delete(mid)
    elapsed = time.time() - t0
    print(f"  delete x{n}: {elapsed:.2f}s ({n/elapsed:.0f} ops/s)")
    return elapsed


async def main():
    print("=" * 60)
    print("Memory Layer Benchmark")
    print("=" * 60)
    results = {}
    results["save"] = await benchmark_save(1000)
    results["retrieve"] = await benchmark_retrieve(500)
    results["delete"] = await benchmark_delete(500)
    print(f"\nSummary: save={results['save']:.2f}s retrieve={results['retrieve']:.2f}s delete={results['delete']:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
