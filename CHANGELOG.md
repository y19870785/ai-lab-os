
## SP-001 - Completed（2026-07-14）

### 架构稳定化

- 新增 `core/system/`，提供不可变 `SystemSettings`、唯一 `create_system()` 和显式 `SystemContainer`。
- CLI、CLI 单次命令、FastAPI lifespan、兼容 Bootstrap 与集成测试统一使用同一套系统 Factory。
- FastAPI dependency 改为读取 `app.state.system`，不再创建空 `ApplicationRuntime`。
- ApplicationRegistry 保存真实应用实例；ApplicationRuntime 只派发已注册实例。
- CEO Assistant 通过统一 MemoryManager 写入 Episodic Memory，API 工作记录与跨重启持久化已验收。
- Workflow、Scheduler、Task、Agent、Tool 与 Provider 由 Composition Root 注入并统一管理生命周期。

### 行为修正

- 删除 ApplicationRuntime 自动创建应用、直接创建 OpenAI Provider 和异常后 Mock Echo。
- Agent 缺少 LLM、Memory 或 ToolExecutor 时显式失败，不再返回成功 Echo。
- Scheduler Job 和 Task 缺少 WorkflowRuntime 时不再标记成功。
- Mock Provider 仅允许在显式 `mock/test` 模式启用；配置不完整时系统状态为 `invalid` 并拒绝启动。
- 修复 OpenAI Compatible LLM/Embedding 的模型配置优先级：显式参数 > `AI_LAB_*` > `OPENAI_*` > 默认值。

### 验证

- Composition Root、真实实例注册、API Memory 写入、跨重启持久化、Scheduler 生命周期和 No Fake Success 测试已新增。
- DeepSeek 真实测试：`5 passed in 9.20s`。
- 全量测试：`735 passed, 26 warnings in 34.06s`。
- PR #1 已合并：https://github.com/y19870785/ai-lab-os/pull/1
- Merge commit：`0a36e250ab8382af6cf3ab3068e432aa69ba3399`
- 架构审查：Approved
- 合并后复核：Passed

---

## [0.32.4] - 2026-07-13

### Interactive First Experience Fix —— 交互式首次体验修复

**问题根因**：`start.bat` 执行 `python -m cli`（无参数），无参数时只打印命令帮助就 `sys.exit(0)`。用户双击后永远看不到交互界面。

**统一 Provider 模式检测**：
- 所有入口统一调用 `core/provider_mode.py` 的 `detect_provider_mode()`
- 返回 `real` / `mock` / `invalid` 三种状态
- 禁止已配 Key 时误报 REAL，禁止未配 Key 时显示 REAL
- start.bat 不再自己实现模式检测

**交互式 CLI**：
- 新增 `cli/ceo.py`：持续交互循环 + Intent Router + 快捷键支持
- 自然语言输入自动路由到工作记录/任务/决策/知识问答
- 支持 `/help` `/brief` `/tasks` `/records` `/decisions` `/knowledge` `/new-session` `/status` `/clear` `/exit`
- `python -m cli ceo` 进入交互模式
- `scripts/start.bat` 双击即进入交互

**API 独立启动入口**：
- 新增 `scripts/start_api.bat`：启动 `uvicorn api.app:app --host 127.0.0.1 --port 8000`
- CLI 和 API 入口完全分离

**修复与回归**：
- pyproject.toml 去除 UTF-8 BOM 头，修复 pytest 无法解析
- 修复 CLI ceo 命令的 MemoryManager 初始化链路
- 全量 712 passed（新增 18 个交互测试），零回归

**DeepSeek 真实交互验证**：通过 ✓
**First Experience Gate**：PASS ✓

---
# 鏇存柊鏃ュ織

## [0.32.3] 鈥?2026-07-13

### CEO Assistant Release Cleanup 鈥?鍙戝竷鍓嶆竻鐞?
**鍏ㄥ眬娴嬭瘯淇**锛?- 鏍瑰洜锛歳eal/ 娴嬭瘯鐨?`load_dotenv()` 灏?`OPENAI_API_KEY` 娉ㄥ叆 `os.environ`锛屾薄鏌撳悗缁櫘閫氭祴璇曠殑 mode detection
- 淇锛氬垱寤?`tests/conftest.py` 鍏ㄥ眬 `isolate_api_keys` fixture + `tests/real/conftest.py` 瑕嗙洊
- 缁撴灉锛氬叏灞€娴嬭瘯浠?692/2 鍒?**699/0 passed**

**涓夌粍闂ㄧ**锛?| 鍛戒护 | Passed | Failed |
|------|--------|--------|
| `pytest tests/ -q -m "not real"` | 694 | 0 |
| `pytest tests/real/ -q -m real` | 5 | 0 |
| `pytest tests/ -q` | **699** | **0** |

**涓€閿惎鍔?*锛歚scripts/start.bat` / `scripts/setup.bat` / `scripts/diagnose.bat` / `scripts/stop.bat`

**Stability Gate**: PASS
**First Experience Gate**: PASS

---

## [0.32.2] 鈥?2026-07-13

### CEO Assistant First Run 鈥?棣栨杩愯绋冲畾鍖?
**娴嬭瘯淇**锛?- 淇 test_task_priority_high 鏂█鍊?(涓啋楂?
- 淇 test_conversation_memory task 璺敱闂
- 淇鍏ㄥ眬 test collection import 椤哄簭鍐茬獊 (recovery/integration)
- 淇 real/ async fixture 閰嶇疆

**娴嬭瘯缁撴灉**锛?- 鍏ㄩ噺 (涓嶅惈 real/): 694 passed, 0 failed, 26 warnings
- Real Provider (鍗曠嫭): 5 passed, 0 failed
- real/ 鍏ㄥ眬妯″紡: 4 涓?async fixture collection error (宸茬煡闄愬埗)

**閰嶇疆鏍囧噯鍖?*锛?- 鏀寔 `AI_LAB_LLM_PROVIDER` 绛夋柊鐜鍙橀噺
- 鍏煎鏃?`OPENAI_API_KEY` 绛夊彉閲?(deprecated)

**涓€閿惎鍔?*锛歚python -m cli chat` 鍙洿鎺ュ惎鍔?CEO Assistant

**Stability Gate**: PASS (鏅€氭祴璇?0 failed, DeepSeek 鐪熷疄楠岃瘉閫氳繃)

---

## [0.32.0] 鈥?2026-07-13

### CEO Assistant MVP 鈥?AI-Lab 棣栦釜鐪熷疄涓氬姟搴旂敤

**浜у搧瀹氫綅**锛氳秴鍝ョ殑涓汉宸ヤ綔鎬绘帶鍔╂墜锛屼粠 Framework First 杞悜 Application First銆?
#### 鏍稿績鑳藉姏锛? 涓棴鐜級

- **宸ヤ綔璁板綍**锛氳嚜鐒惰瑷€杈撳叆 鈫?瀹炰綋鎻愬彇锛堟棩鏈?瀵硅薄/浜嬮」/鐘舵€?鏍囩锛夆啋 Episodic Memory 瀛樺偍
- **寰呭姙浠诲姟**锛氬垱寤轰换鍔?鈫?鎴鏃堕棿/浼樺厛绾?鐘舵€佺鐞?鈫?鏌ヨ/鏇存柊/瀹屾垚
- **鍐崇瓥璁板綍**锛氬喅绛栬鏄?鈫?trigger/alternatives/chosen/reason 鎻愬彇 鈫?Decision Memory 瀛樺偍
- **鐭ヨ瘑闂瓟**锛氭枃妗ｅ鍏?鈫?Chunk/Embedding/Vector 鈫?Hybrid Retrieval 鈫?寮曠敤鏉ユ簮
- **姣忔棩绠€鎶?*锛氬熀浜庣湡瀹?Task/Memory 鏁版嵁 鈫?寰呭姙/閫炬湡/宸ヤ綔璁板綍/鍐崇瓥/寤鸿浼樺厛绾?- **澶氳疆瀵硅瘽**锛歋ession 涓婁笅鏂?+ Memory 鍥炴函 + LLM 鐢熸垚

#### CLI 鍛戒护锛堟柊澧?5 涓級

```bash
python -m cli brief          # 姣忔棩绠€鎶?python -m cli log <鍐呭>      # 璁板綍宸ヤ綔
python -m cli task <鍐呭>     # 鍒涘缓/鏌ョ湅浠诲姟
python -m cli decide <鍐呭>   # 璁板綍鍐崇瓥
python -m cli chat <娑堟伅>     # 澶氳疆瀵硅瘽
```

#### REST API锛堟柊澧?4 涓矾鐢憋級

- `POST /work-logs` 鈥?宸ヤ綔璁板綍
- `POST /decisions` 鈥?鍐崇瓥璁板綍
- `GET /brief` 鈥?姣忔棩绠€鎶?- `POST /knowledge/ask` 鈥?鐭ヨ瘑闂瓟

#### 鏂板鏂囦欢

- `applications/ceo_assistant/` 鈥?CEO Assistant 搴旂敤锛坅pplication.py / manifest.yaml / prompts / README锛?- `product/` 鈥?浜у搧鏂囨。锛圴ISION / REQUIREMENTS / USE_CASES / BUSINESS_WORKFLOWS / PRODUCT_ROADMAP锛?- `cli/commands/{brief,log,task,decide,ask}_cmd.py` 鈥?CEO Assistant CLI 鍛戒护
- `api/routes/{work_logs,decisions,brief,knowledge}.py` 鈥?REST API 璺敱
- `core/providers/embedding/local.py` 鈥?鏈湴 SentenceTransformer Embedding Provider

#### 淇

- DatabaseManager bootstrap 鍒濆鍖栦慨澶嶏紙`_noop`锛?- KnowledgeManager bootstrap 鏋勯€犲弬鏁颁慨澶?- Chroma Vector Provider metadata 绌?dict 淇
- CLI 缂栫爜缁熶竴 UTF-8
- CEO Assistant 鎰忓浘妫€娴嬩紭鍏堢骇淇锛堝喅绛?> 浠诲姟 > 宸ヤ綔璁板綍锛?- MemoryManager.save_memory 璋冪敤鎺ュ彛瀵归綈

#### 鐪熷疄 Provider 楠岃瘉

| 缁勪欢 | 鐘舵€?|
|------|------|
| DeepSeek LLM (deepseek-chat V3) | 鉁?generate / streaming / 澶氳疆 |
| 鏈湴 Embedding (SentenceTransformer) | 鉁?384d, all-MiniLM-L6-v2 |
| Chroma Vector Store | 鉁?insert / search / metadata |
| Document QA Pipeline | 鉁?ingest 鈫?chunk 鈫?embed 鈫?search |
| Personal Assistant Demo | 鉁?3 杞璇?+ Episodic Memory |

#### 娴嬭瘯

- 鍏ㄩ噺 647 娴嬭瘯闆跺洖褰?
---

## [0.31.0] - 2026-07-13

### Alpha Field Validation

- 缁熶竴鍚姩鍏ュ彛銆佺幆澧冮厤缃€佹寔涔呭寲楠岃瘉銆佹晠闅滄敞鍏ャ€佸彲瑙傛祴鎬с€丗ield Demo
- 647 娴嬭瘯

---

<details>
<summary>鍘嗗彶鐗堟湰 (v0.1.0 鈥?v0.30.0)</summary>

## [0.30.0] 鈥?Application Foundation & Alpha Deployment
## [0.23.0] 鈥?Multi-Agent Coordination
## [0.22.0] 鈥?Task Runtime
## [0.21.0] 鈥?Scheduler Runtime
## [0.20.0] 鈥?Workflow Engine
## [0.19.0] 鈥?MCP Adapter + End-to-End Integration
## [0.18.0] 鈥?Tool System
## [0.17.0] 鈥?Agent Runtime
## [0.16.0] 鈥?Knowledge Layer
## [0.15.0] 鈥?Provider Layer
## [0.14.0] 鈥?Architecture Stabilization
## [0.13.0] 鈥?Core & Memory Stabilization
## [0.12.0] 鈥?Memory Layer Integration
## [0.11.0] 鈥?Semantic & Decision Memory
## [0.10.0] 鈥?Episodic Memory
## [0.9.0] 鈥?Memory Consolidation Engine
## [0.8.0] 鈥?Session Memory Implementation
## [0.7.0] 鈥?Core Runtime Implementation
## [0.6.1] 鈥?Decision Memory 鏋舵瀯璁捐
## [0.5.0] 鈥?Governance Layer
## [0.4.0] 鈥?Knowledge Layer 鏋舵瀯璁捐
## [0.3.0] 鈥?Agent Architecture
## [0.2.0] 鈥?Memory Layer 鏋舵瀯璁捐
## [0.1.0] 鈥?Core Layer 鏋舵瀯璁捐

</details>
