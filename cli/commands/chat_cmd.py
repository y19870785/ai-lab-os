"""AI-Lab CLI —— 单次对话命令。"""

from cli.runtime import execute_ceo_request


async def run(args):
    user_input = " ".join(args) if args else "Hello"
    response, mode = await execute_ceo_request(user_input)
    print(f"\n[CEO Assistant | {mode.upper()}]")
    print(response.answer or response.error)
    print(f"\n[{response.latency_ms:.0f}ms | trace: {response.trace_id[:8]}]")
