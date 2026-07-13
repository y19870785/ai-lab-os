"""交互式 CEO Assistant CLI —— 持续对话模式。

用法：
    python -m cli ceo

启动后进入交互循环，支持：
- 自然语言输入（自动路由到工作记录/任务/决策/聊天）
- /help /brief /tasks /records /decisions /knowledge /new-session /status /clear /exit
"""

import asyncio
import io
import os
import sys
from dotenv import load_dotenv
load_dotenv()

# 强制 stdin/stdout 为 UTF-8，解决 Windows 管道中文乱码（pytest 下 stdin 可能不可 reconfigure）
try:
    import sys
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from core.provider_mode import detect_provider_mode, get_provider_info


HELP_TEXT = """
可用命令：
  /help          显示帮助
  /brief         今日简报
  /tasks         查看待办任务
  /records       查看工作记录
  /decisions     查看决策记录
  /knowledge <问题>  知识检索
  /new-session   开始新会话
  /status        系统状态
  /clear         清屏
  /exit          退出

普通输入会自动识别意图（工作记录/任务/决策/问答）。
输入 / 开头的命令直接执行，其他输入走意图路由。
"""


def _detect_intent(text: str) -> str:
    """基于关键词规则识别用户意图。"""
    text_lower = text.lower().strip()
    if text_lower.startswith("/"):
        return "command"

    brief_kw = ["简报", "今日总结", "今天做了什么", "今天的工作", "今日概览", "daily brief", "工作概览"]
    if any(kw in text_lower for kw in brief_kw):
        return "brief"

    decision_kw = ["决定", "决策", "选择", "采用", "确认使用", "不先做", "放弃"]
    if any(kw in text_lower for kw in decision_kw):
        return "decision"

    task_kw = ["任务", "待办", "提醒我", "todo", "task", "截止", "cancel task"]
    if any(kw in text_lower for kw in task_kw):
        return "task"

    knowledge_kw = ["什么是", "解释", "法规", "标准", "规定", "文档", "查询", "查找"]
    if any(kw in text_lower for kw in knowledge_kw):
        return "knowledge"

    log_kw = ["记录", "今天", "刚才", "完成了", "确认了", "收到了", "会议", "见了"]
    if any(kw in text_lower for kw in log_kw):
        return "work_log"

    return "chat"


async def _init_app():
    """初始化 CEOAssistant，复用 log_cmd 等子命令的初始化链路。"""
    from core.bus.bus import get_bus
    from core.memory.manager import MemoryManager
    from core.memory.models import MemoryType
    from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
    from core.memory.session import SessionMemory
    from core.memory.storage.sqlite_semantic import SQLiteSemanticStore
    from core.memory.storage.sqlite_decision import SQLiteDecisionStore
    from applications.ceo_assistant.application import CEOAssistant

    data_dir = os.path.join(os.getcwd(), "data", "sqlite")
    os.makedirs(data_dir, exist_ok=True)

    bus = get_bus()
    await bus.start()

    memory = MemoryManager(bus=bus)
    memory.register_store(MemoryType.SESSION, SessionMemory(default_ttl=3600, bus=bus))

    es = SQLiteEpisodicStore(db_path=os.path.join(data_dir, "episodic.db"))
    await es.initialize()
    memory.register_store(MemoryType.EPISODIC, es)

    try:
        ss = SQLiteSemanticStore(db_path=os.path.join(data_dir, "semantic.db"))
        await ss.initialize()
        memory.register_store(MemoryType.SEMANTIC, ss)
    except Exception:
        pass

    try:
        ds = SQLiteDecisionStore(db_path=os.path.join(data_dir, "decision.db"))
        await ds.initialize()
        memory.register_store(MemoryType.DECISION, ds)
    except Exception:
        pass

    # 初始化 LLM Provider（DeepSeek）
    llm = None
    try:
        from core.providers.llm.openai import OpenAILLMProvider
        llm = OpenAILLMProvider()
        await llm.initialize()
    except Exception as e:
        import sys
        print(f"[WARN] LLM 初始化失败，将使用离线模式：{e}", file=sys.stderr)

    app = CEOAssistant(memory_manager=memory, llm_provider=llm)
    return app, bus, memory, llm


async def _handle_command(app, cmd: str, args: str):
    """执行 / 开头的快捷命令。"""
    from applications.models import ApplicationRequest

    if cmd in ("exit", "quit"):
        return None
    elif cmd == "help":
        return HELP_TEXT.strip()
    elif cmd == "brief":
        resp = await app.run(ApplicationRequest(
            application_name="ceo-assistant", user_input="简报"))
        return resp.answer if resp and resp.answer else "暂无简报。"
    elif cmd == "tasks":
        resp = await app.run(ApplicationRequest(
            application_name="ceo-assistant", user_input="查看待办任务"))
        return resp.answer if resp and resp.answer else "暂无待办任务。"
    elif cmd == "records":
        resp = await app.run(ApplicationRequest(
            application_name="ceo-assistant", user_input="查看工作记录"))
        return resp.answer if resp and resp.answer else "暂无工作记录。"
    elif cmd == "decisions":
        resp = await app.run(ApplicationRequest(
            application_name="ceo-assistant", user_input="查看决策记录"))
        return resp.answer if resp and resp.answer else "暂无决策记录。"
    elif cmd == "knowledge":
        if not args.strip():
            return "用法：/knowledge <问题>"
        resp = await app.run(ApplicationRequest(
            application_name="ceo-assistant", user_input=args.strip()))
        return resp.answer if resp and resp.answer else "未找到相关知识。"
    elif cmd == "new-session":
        return "新会话已开始。"
    elif cmd == "status":
        info = get_provider_info()
        return (
            f"AI-Lab CEO Assistant v0.32.4\n"
            f"运行模式：{info['mode'].upper()}\n"
            f"Provider：{info['provider']}\n"
            f"模型：{info['model']}\n"
            f"Base URL：{info['base_url']}"
        )
    elif cmd == "clear":
        os.system("cls" if os.name == "nt" else "clear")
        return ""
    else:
        return f"未知命令：/{cmd}。输入 /help 查看可用命令。"


async def run_ceo():
    """交互式 CEO Assistant 主循环。"""
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

    info = get_provider_info()

    print("=" * 40)
    print(f"  AI-Lab CEO Assistant v0.32.4")
    print(f"  运行模式：{info['mode'].upper()}")
    if info["mode"] == "real":
        print(f"  Provider：{info['provider']}")
        print(f"  Base URL：{info['base_url']}")
        print(f"  模型：{info['model']}")
        print(f"  API Key：{info['api_key_masked']}")
    else:
        print(f"  提示：当前未配置真实 API Key，所有回复均为模拟结果。")
    print(f"  Workspace：personal")
    print("=" * 40)
    print()
    print("输入 /help 查看命令，/exit 退出。")
    print()

    app, bus, memory, llm = await _init_app()

    try:
        while True:
            try:
                user_input = input("超哥 > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                parts = user_input[1:].split(None, 1)
                cmd = parts[0].lower()
                a = parts[1] if len(parts) > 1 else ""
                result = await _handle_command(app, cmd, a)
                if result is None:
                    print("再见！")
                    break
                if result:
                    print(result)
                continue

            # 意图路由
            intent = _detect_intent(user_input)
            from applications.models import ApplicationRequest
            prefix_map = {
                "work_log": "记录: ", "task": "任务: ",
                "decision": "决策: ", "knowledge": "知识: ",
                "brief": "", "chat": "",
            }
            prefix = prefix_map.get(intent, "")
            req = ApplicationRequest(
                application_name="ceo-assistant",
                user_input=f"{prefix}{user_input}",
            )
            try:
                resp = await app.run(req)
                if resp and resp.answer:
                    print(resp.answer)
                else:
                    print("(无响应)")
            except Exception as e:
                print(f"[错误] {e}")
    finally:
        try:
            await bus.stop()
        except Exception:
            pass
        try:
            if llm:
                await llm.shutdown()
        except Exception:
            pass

    print("CEO Assistant 已关闭。")


if __name__ == "__main__":
    asyncio.run(run_ceo())
