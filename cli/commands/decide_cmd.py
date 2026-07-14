"""CEO Assistant CLI —— 决策命令。"""

from cli.runtime import execute_ceo_request


async def run(args):
    user_input = " ".join(args) if args else ""
    if not user_input:
        print("Usage: python -m cli decide <决策内容>")
        return
    response, mode = await execute_ceo_request(f"决定: {user_input}")
    print(f"\n[CEO Assistant | {mode.upper()}]")
    print(response.answer or response.error)
