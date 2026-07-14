"""CEO Assistant CLI —— 知识问答命令。"""

from cli.runtime import execute_ceo_request


async def run(args):
    user_input = " ".join(args) if args else ""
    if not user_input:
        print("Usage: python -m cli ask <问题>")
        return
    response, mode = await execute_ceo_request(f"知识: {user_input}")
    print(f"\n[CEO Assistant | {mode.upper()}]")
    print(response.answer or response.error)
    if response.citations:
        print(f"\n引用来源: {', '.join(response.citations)}")
