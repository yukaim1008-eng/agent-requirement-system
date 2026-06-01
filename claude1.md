你是一位资深AI工程师，我正在做一个“多Agent协作自动化需求分析”的项目，需要你协助我用Python实现。我会使用云端LLM（GPT-4o-mini或DeepSeek）和你协同开发。

## 项目定位
模拟IT项目启动阶段的需求分析流程：用户输入一句模糊需求，由多个AI Agent分工协作，最终产出结构化的需求规格说明书（含功能清单、用户故事、竞品分析、技术可行性评估）。

## 技术栈
- 多Agent框架：CrewAI（主要，上手快）或 LangGraph
- LLM：云端模型API（GPT-4o-mini 或 DeepSeek，由我提供Key）
- 工具集成：Tavily搜索API（给行业研究Agent联网搜索用）、文件读写工具
- 界面：Streamlit（展示多Agent对话和最终文档下载）
- 文档导出：python-docx 或 markdown 库，生成需求规格说明书

## 整体架构（Agent角色与协作流程）
### Agent角色定义（5个）
1. **协调员Agent**（Coordinator）
   - 接收用户原始需求，拆解成子任务
   - 按逻辑顺序调度其他Agent，整合输出
   - 决定何时需要人在回路（Human-in-the-loop），暂停等待用户确认

2. **需求分析师Agent**（Requirements Analyst）
   - 深度挖掘需求，通过追问补全模糊点
   - 输出功能需求列表、用户故事（User Story）
   - 可接受技术评估Agent的质疑，修改不合理需求

3. **行业研究员Agent**（Industry Researcher）
   - 使用Tavily搜索工具，查找同类产品、竞品、行业合规要求
   - 汇总调研结果，提炼关键参考信息

4. **技术评估员Agent**（Technical Evaluator）
   - 从技术实现角度评估每个需求点的可行性、风险、工作量
   - 给出建议技术栈、架构约束和工期预估
   - 可主动向需求分析师Agent提出修改建议（Agent间互问）

5. **文档专员Agent**（Document Specialist）
   - 收集所有前序输出，整理成标准需求规格说明书
   - 生成Markdown或Word文件，供最终下载

### 协作流程（示例）
用户输入 → 协调员拆解 → 
  (并行/串行) 需求分析师+行业研究员+技术评估员工作 →
  Agent间可能的互问（如技术评估员质疑需求可行性）→ 
  人在回路确认关键决策 → 
  文档专员汇总生成说明书 → 
  界面展示并支持下载

### 高阶特性
- Agent间互问机制：技术评估员可向需求分析师发问“该需求时间紧、风险高，能否简化？”需求分析师再修改
- 人在回路（Human-in-the-loop）：关键节点（如需求优先级排序）暂停，让用户在Streamlit界面确认后再继续
- 联网搜索：行业研究员调用Tavily Search API获取真实网络数据
- 项目联动加分：技术评估员内部可调用项目一（IT运维知识库）的高阶RAG接口，查询历史项目经验，辅助当前评估（接口预留即可，不必强依赖）

## 文件拆分
请严格按以下文件组织，每个文件职责单一：
- `config.py`：API Key（LLM、Tavily）、模型选择、Agent角色定义模板、输出路径等集中配置
- `agents.py`：所有Agent的创建（CrewAI的Agent定义、角色提示词、工具绑定）
- `tasks.py`：定义每个Agent执行的任务（CrewAI的Task），包含上下文传递逻辑
- `crew_runner.py`：核心运行脚本，初始化Crew，启动协作流程，返回结果
- `tools.py`：自定义工具（如搜索工具封装、文档生成工具、可扩展的RAG查询接口占位）
- `main.py`：Streamlit界面，展示各Agent对话气泡、任务进度，提供文档下载按钮
- `utils.py`：通用工具函数（日志、格式化、状态管理）


## 开发顺序建议
1. 先完成 `config.py` 和 `agents.py`，定义好所有Agent角色和核心提示词
2. 再开发 `tasks.py` 和 `crew_runner.py`，跑通最简单的顺序协作
3. 加入 `tools.py` 联网搜索功能，实现Agent间互问和人在回路
4. 最后用 `main.py` 做Streamlit界面，优化多Agent对话展示和文档下载

## 代码风格要求
- 中文注释清晰，解释关键逻辑
- CrewAI的Agent和Task定义应易于修改角色描述，以适应不同业务场景
- 文档专员生成的说明书应包含：项目背景、功能需求清单、用户故事、竞品分析摘要、技术评估建议
- 所有Agent的提示词（System Prompt）应集中在config中管理，便于调优