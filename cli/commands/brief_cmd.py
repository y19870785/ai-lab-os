"""CEO Assistant CLI —— 每日简报命令。"""

from cli.runtime import execute_ceo_request


async def run(args):
    response, mode = await execute_ceo_request("今日简报")
    print(f"\n[CEO Assistant | {mode.upper()}]")
    print(response.answer or response.error)
