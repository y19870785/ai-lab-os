"""Tool Demo —— 验证 Tool Runtime 完整链路。

演示：注册 -> 执行 -> 审计 -> 指标
"""

import asyncio
import sys
sys.path.insert(0, ".")

from core.tools.registry import ToolRegistry
from core.tools.executor import ToolExecutor
from core.tools.builtin.echo import EchoTool
from core.tools.builtin.calculator import CalculatorTool
from core.tools.builtin.datetime_tool import DateTimeTool
from core.tools.builtin.uuid_tool import UUIDTool
from core.tools.models import ToolRequest
from core.tools.audit import ToolAuditLogger
from core.tools.metrics import ToolMetrics


async def main():
    print("=" * 60)
    print("Tool Runtime Demo")
    print("=" * 60)

    # Setup
    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    audit = ToolAuditLogger()
    metrics = ToolMetrics()

    # Register tools
    for tool in [EchoTool(), CalculatorTool(), DateTimeTool(), UUIDTool()]:
        registry.register(tool.info, tool.__class__)
        print(f"  [OK] Registered: {tool.info.name}")

    # Execute tools
    tests = [
        ("echo", {"text": "Hello, AI-Lab!"}),
        ("calculator", {"expression": "2 + 3 * 4"}),
        ("datetime", {"format": "iso"}),
        ("uuid", {}),
    ]

    print("\n--- Execution Results ---")
    for tool_name, args in tests:
        req = ToolRequest(tool_name=tool_name, arguments=args)
        result = await executor.execute(req)
        audit.log(tool_name, args, result)
        metrics.record(tool_name, result)
        status = "OK" if result.success else "FAILED"
        print(f"  [{status}] {tool_name}({args}): {result.output[:80] if result.output else result.error}")

    print("\n--- Metrics ---")
    print(f"  Calls: {metrics.total_calls}")
    print(f"  Success Rate: {metrics.success_rate():.1%}")
    print(f"  By Tool: {metrics.by_tool()}")

    print("\n" + "=" * 60)
    print("Tool Runtime Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
