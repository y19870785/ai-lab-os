"""AI-Lab CLI —— 命令行入口。"""
import sys
import asyncio
from cli.commands import agenda_cmd, health_cmd, chat_cmd, run_cmd, inspect_cmd
from cli.commands import brief_cmd, log_cmd, task_cmd, decide_cmd, ask_cmd
from cli.commands import reminder_status_cmd
from cli.commands import reminders_cmd
from cli.commands import reminder_cancel_cmd, reminder_reschedule_cmd
from cli.commands import inbox_cmd
from core.errors import FailureException


COMMANDS = {
    "health": health_cmd.run,
    "chat": chat_cmd.run,
    "run": run_cmd.run,
    "inspect": inspect_cmd.run,
    "brief": brief_cmd.run,
    "log": log_cmd.run,
    "task": task_cmd.run,
    "decide": decide_cmd.run,
    "ask": ask_cmd.run,
    "reminder-status": reminder_status_cmd.run,
    "agenda": agenda_cmd.run,
    "reminders": reminders_cmd.run,
    "reminder-cancel": reminder_cancel_cmd.run,
    "reminder-reschedule": reminder_reschedule_cmd.run,
    "inbox": inbox_cmd.run,
    "ceo": "ceo",  # 特殊处理：交互式 CLI，不走单次命令模式
}


def main():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        print("AI-Lab CLI - CEO Assistant")
        print("=" * 40)
        print()
        print("交互式模式：")
        print("  python -m cli ceo        启动交互式 CEO Assistant")
        print()
        print("单次命令：")
        print("  brief        每日简报")
        print("  log <内容>    记录工作")
        print("  task <内容>   创建/查看任务")
        print("  decide <内容>  记录决策")
        print("  ask <问题>    知识问答")
        print("  chat <消息>   多轮对话")
        print("  health       系统健康检查")
        print("  inspect      系统状态")
        print("  reminder-status <ID>  查询站内提醒状态")
        print("  reminders             查看站内提醒列表")
        print("  reminder-cancel <ID>  取消提醒")
        print("  reminder-reschedule <ID> --scheduled-for <ISO>  改期提醒")
        print()
        print("Examples:")
        print('  python -m cli brief')
        print('  python -m cli log "今天和张经理确认了蜂蜡检测方案"')
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # ceo 是交互式命令，特殊处理
    if cmd == "ceo":
        from cli.ceo import run_ceo
        asyncio.run(run_ceo())
        return

    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print('试试: python -m cli ceo  (交互式模式)')
        sys.exit(1)

    handler = COMMANDS[cmd]
    try:
        if asyncio.iscoroutinefunction(handler):
            asyncio.run(handler(args))
        else:
            handler(args)
    except FailureException as exc:
        print(f"{exc.failure.code}: {exc.failure.message}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
