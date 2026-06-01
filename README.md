# 多 Agent 协作 —— 自动化需求分析系统

> 一句模糊需求 → 5 个 AI Agent 分工协作 → 一份专业的需求规格说明书（PRD），支持一键下载 Word。

把"做一个校园二手交易小程序"这样的一句话，交给 5 个有明确分工的 AI Agent：协调员拆解任务、需求分析师挖需求、行业研究员调研竞品、技术评估员评可行性、文档专员汇总成 PRD。核心不是"调一次大模型"，而是一条**可编排、可质疑、可人工干预、可跨系统联动**的 AI 工作流。

---

## ✨ 核心亮点

| # | 亮点 | 说明 |
|---|------|------|
| 1 | **Agent 互质疑反馈环** | 技术评估员若判定需求"风险高/不可行"，会输出标准化结论自动**退回需求分析师修订**，修订后重新评估，直到通过或达到最大轮数（防死循环） |
| 2 | **人在回路（Human-in-the-loop）** | 在"需求分析"这一关键节点暂停，用户可在界面**审阅、编辑、补充**后再确认进入耗时的下游阶段 |
| 3 | **跨系统联动** | 技术评估员通过子进程调用**自建的高阶 RAG（IT 运维知识库）**查询历史经验，带引用溯源；进程隔离、失败优雅降级 |
| 4 | **降级设计** | 联网搜索有 Tavily Key 走真实搜索、无 Key 自动降级为 LLM 模拟；RAG 不可用时回退通用经验，绝不阻断主流程 |

---

## 🏗️ 架构

```
                          ┌─────────────────────────────┐
                          │   Streamlit 界面 (main.py)   │
                          │  输入 / 人在回路确认 / 下载   │
                          └──────────────┬──────────────┘
                                         │ on_stage 实时回调
                          ┌──────────────▼──────────────┐
                          │   编排核心 core/crew_runner   │
                          │  分阶段执行 + 互质疑反馈环    │
                          └──────────────┬──────────────┘
              ┌───────────────┬──────────┼──────────┬───────────────┐
              ▼               ▼          ▼          ▼               ▼
        🧭 协调员       📋 需求分析师  🔍 行业研究员 🛠️ 技术评估员   📄 文档专员
                                          │            │
                                   web_search 工具  query_knowledge_base 工具
                                          │            │
                                   Tavily / LLM    子进程 JSON 协议
                                     模拟降级            │
                                                  ┌──────▼─────────┐
                                                  │ 自建 RAG 项目   │
                                                  │ (it-ops-rag)    │
                                                  │ backend.py 常驻 │
                                                  └────────────────┘
        （5 个 Agent 共用同一个 DeepSeek LLM，仅靠角色提示词区分身份 —— 1 个 Key 即可）
```

## 🧩 协作流程

```
用户需求
  └─► 🧭 协调拆解
        └─► 📋 需求分析 ──►【👤 人在回路：审阅/编辑/确认】
                                └─► 🔍 行业研究
                                      └─► 🛠️ 技术评估
                                            ├─ 通过 ───────────────┐
                                            └─ 需修订 ►📋修订►🛠️重评 ┤ (最多 N 轮)
                                                                   ▼
                                                            📄 文档汇总 ──► 📥 导出 Word
```

## 📁 文件结构

```
agent-requirement-system/
├── main.py              # Streamlit 入口（两段式人在回路 + 实时进度 + 下载）
├── config.py            # 全局配置：5 个角色提示词、LLM 工厂、互质疑轮数
├── agents/builder.py    # 创建 5 个 Agent（按角色绑定工具）
├── tasks/builder.py     # 分阶段任务构建器（评估任务带"可行性结论"标记）
├── tools/
│   ├── search_tool.py   # 联网搜索（Tavily / LLM 模拟降级）
│   ├── rag_tool.py      # RAG 子进程查询（常驻复用 + 真超时，不阻塞）
│   └── doc_tool.py      # Markdown PRD → Word 导出
├── core/crew_runner.py  # 编排：analyze_requirement / generate_prd / run_crew
├── utils/helpers.py     # 日志等
└── output/              # 生成的 PRD（.docx）
```

## 🛠️ 技术栈

Python 3.13 · **CrewAI 1.14** · DeepSeek API · Tavily Search · Streamlit · python-docx
（联动：自建 RAG 项目 `it-ops-rag` —— LangChain / Qdrant / BGE-large / bge-reranker）

## 🚀 运行

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. 配置 .env（复用同一个 DeepSeek Key 驱动全部 5 个 Agent）
#    DEEPSEEK_API_KEY=sk-xxx
#    TAVILY_API_KEY=            # 可留空，自动降级为 LLM 模拟
#    RAG_DIR=...\it-ops-rag     # 可选，技术评估员联动用
#    RAG_PYTHON=...\it-ops-rag\.venv\Scripts\python.exe

# 3. 启动界面
streamlit run main.py
```

打开 http://localhost:8501 → 输入需求 → ① 分析 → 审阅确认 → ② 生成 → 下载 PRD。

> 想看「互质疑」触发：输入过度承诺的需求，如"2 周内做企业级 IT 运维监控平台，支持全链路追踪、AI 预测、自动自愈、多云管理"。

## 🔗 与 RAG 项目的联动原理

技术评估员调用 `query_knowledge_base` 工具时，本系统用 **RAG 项目自己的 venv** 拉起其 `backend.py` 子进程，走 **JSON 行协议** 通信（`{"query":...}` → `{"answer":..., "citations":[...]}`）。这样 RAG 的重模型（BGE / reranker / torch）完全隔离在独立进程，不污染本项目依赖；后端进程常驻复用，避免每次重复加载模型。

## 🧪 踩过的坑与解决

1. **CrewAI + DeepSeek 工具名必须 ASCII**：DeepSeek 走 OpenAI 兼容接口，函数名只能含 `字母/数字/_/-`，中文工具名会被清空 → `function name cannot be empty`。
2. **subprocess `readline()` 阻塞陷阱**：用 `readline()` 读子进程响应、外层套 `timeout` 循环是无效的——`readline` 会一直阻塞，timeout 永远检查不到，导致整个流程卡死。改用「后台读取线程 + 队列 + `queue.get(timeout=)`」，卡住即超时杀进程走降级。
3. **多 Agent ≠ 多 Key**：5 个 Agent 共用同一个 DeepSeek LLM，角色差异只来自不同的 System Prompt。
4. **互质疑要可控**：用评估员输出的标准化结论标记（`可行性结论：通过 / 需修订 || 原因`）做显式反馈环，比依赖 CrewAI 自动 hierarchical 更透明、可演示。
