"""CEO Assistant CLI —— 任务命令。"""

from cli.runtime import execute_ceo_request


async def run(args):
    user_input = " ".join(args) if args else "查看我的待办任务"
    response, mode = await execute_ceo_request(user_input)
    print(f"\n[CEO Assistant | {mode.upper()}]")
    print(response.answer or response.error)
