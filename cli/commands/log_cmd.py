"""CEO Assistant CLI —— 工作记录命令。"""

from cli.runtime import execute_ceo_request


async def run(args):
    user_input = " ".join(args) if args else ""
    if not user_input:
        print("Usage: python -m cli log <工作内容>")
        return
    response, mode = await execute_ceo_request(f"记录: {user_input}")
    print(f"\n[CEO Assistant | {mode.upper()}]")
    print(response.answer or response.error)
