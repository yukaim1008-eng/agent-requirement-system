"""
任务定义层 —— 分阶段任务构建器（每个阶段单独构建 Task）

阶段 4：改为分阶段执行，上游产出以文本形式注入下游任务描述，便于：
  - 技术评估员↔需求分析师的互质疑反馈环
  - 人在回路在阶段之间插入
  - Streamlit 逐阶段展示
关键：技术评估任务要求最后一行输出标准的「可行性结论」标记，供编排层解析是否需退回修订
"""
from crewai import Task


def make_coordination_task(agent, user_requirement: str) -> Task:
    """协调员：把需求拆解成给团队的调度计划。"""
    return Task(
        description=(
            f"用户的原始需求是：'{user_requirement}'。\n"
            "作为项目协调员，请把它拆解成给团队的子任务清单（调度计划），"
            "说明需求分析师、行业研究员、技术评估员、文档专员各自要产出什么。"
            "简明扼要，5-8 行即可。"
        ),
        expected_output="一份简短的任务拆解与调度计划",
        agent=agent,
    )


def make_analysis_task(agent, user_requirement: str, feedback: str = "") -> Task:
    """需求分析师：分析需求；若带 feedback 则按技术评估意见修订。"""
    desc = (
        f"用户提出的原始需求是：'{user_requirement}'。\n"
        "请深入分析这个需求：\n"
        "1. 识别核心目标用户和典型使用场景\n"
        "2. 列出功能需求清单（区分主要功能 / 次要功能）\n"
        "3. 用标准格式写出 5-8 条用户故事（作为<角色>，我想要<功能>，以便<价值>）\n"
        "如有模糊点，明确列出你的合理假设。"
    )
    if feedback:
        desc += (
            "\n\n【技术评估员的修订意见】上一轮分析中，以下需求被判定为风险高 / 不可行，"
            f"请据此调整、简化或替换，并重新输出修订后的需求分析：\n{feedback}"
        )
    return Task(
        description=desc,
        expected_output="结构化需求分析：功能清单 + 用户故事 + 关键假设",
        agent=agent,
    )


def make_research_task(agent, analysis_text: str) -> Task:
    """行业研究员：基于需求分析做竞品调研（可用搜索工具）。"""
    return Task(
        description=(
            "以下是需求分析的产出：\n----\n" + analysis_text + "\n----\n\n"
            "基于它，调研这个产品方向：\n"
            "1. 2-3 个同类产品 / 竞品及其核心特点与差异\n"
            "2. 该领域常见的功能模式和用户期待\n"
            "3. 需要注意的行业合规 / 安全要求（如有）\n"
            "如需获取竞品信息，请使用你的『行业竞品联网搜索』工具。最后提炼出关键参考信息。"
        ),
        expected_output="竞品分析摘要 + 行业参考信息",
        agent=agent,
    )


def make_evaluation_task(agent, analysis_text: str, research_text: str) -> Task:
    """技术评估员：评估可行性（可查 RAG），并给出标准格式的可行性结论。"""
    return Task(
        description=(
            "需求分析：\n----\n" + analysis_text + "\n----\n\n"
            "竞品调研：\n----\n" + research_text + "\n----\n\n"
            "请从技术实现角度评估：\n"
            "1. 各主要功能的技术可行性与难度（高 / 中 / 低）\n"
            "2. 建议的技术栈和整体架构\n"
            "3. 主要技术风险点\n"
            "4. 工作量 / 工期预估\n"
            "如对某类技术问题（如运维、排障、性能）没把握，可使用『历史项目经验查询』工具参考知识库。\n"
            "如发现需求时间紧 / 风险高 / 明显不可行，请明确指出并给出简化建议。\n\n"
            "【重要】必须在回答的最后单独一行给出结论，严格使用以下两种格式之一：\n"
            "可行性结论：通过\n"
            "可行性结论：需修订 || <一句话说明哪些需求需要简化或调整>"
        ),
        expected_output="技术评估报告，且最后一行为标准格式的可行性结论",
        agent=agent,
    )


def make_documentation_task(agent, analysis_text: str, research_text: str, evaluation_text: str) -> Task:
    """文档专员：汇总成完整 PRD。"""
    return Task(
        description=(
            "请汇总以下三份产出，整理成一份完整、专业的需求规格说明书（PRD）。\n\n"
            "需求分析：\n----\n" + analysis_text + "\n----\n\n"
            "竞品调研：\n----\n" + research_text + "\n----\n\n"
            "技术评估：\n----\n" + evaluation_text + "\n----\n\n"
            "PRD 必须包含以下章节：\n"
            "1. 项目背景与目标\n2. 功能需求清单\n3. 用户故事\n"
            "4. 竞品分析摘要\n5. 技术可行性评估与建议\n"
            "用 Markdown 格式输出，章节层级清晰、措辞专业。"
            "不要把上面的『可行性结论』标记原样写进 PRD。"
        ),
        expected_output="一份完整的 Markdown 格式需求规格说明书（PRD）",
        agent=agent,
    )
