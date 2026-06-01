"""
编排核心层 —— 分阶段驱动多 Agent 协作，含「互质疑反馈环」与「人在回路」

对外接口：
  analyze_requirement(req)            → 阶段一：协调拆解 + 需求分析（供人工确认）
  generate_prd(req, analysis)         → 阶段二：研究→评估→互质疑→文档→导出
  run_crew(req)                       → 一把梭（命令行/无人工干预时用）

设计：分阶段单任务执行 + 手动传递上下文，换取对反馈环和人工干预点的完全控制
（比 CrewAI 自动 hierarchical 更透明、可演示、易接入 Streamlit）
"""
import re
from datetime import date

from crewai import Crew, Process

from config import MAX_REVISION_ROUNDS
from agents.builder import build_agents
from tasks.builder import (
    make_coordination_task,
    make_analysis_task,
    make_research_task,
    make_evaluation_task,
    make_documentation_task,
)
from tools.doc_tool import export_prd_to_docx


def _run_single(agent, task) -> str:
    """用单 Agent 单任务的 Crew 执行一个阶段，返回文本产出。"""
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    return str(crew.kickoff())


def _parse_verdict(evaluation_text: str):
    """从技术评估产出里解析可行性结论。返回 ("通过" | "需修订", feedback_str)。"""
    for line in reversed(evaluation_text.splitlines()):
        if "可行性结论" in line:
            if "需修订" in line:
                feedback = line.split("||", 1)[1].strip() if "||" in line else "请重新审视高风险需求"
                return "需修订", feedback
            return "通过", ""
    return "通过", ""


def analyze_requirement(user_requirement: str, on_stage=None) -> dict:
    """
    阶段一：协调拆解 + 需求分析。产出供人工确认后再进入阶段二。

    Returns: {"plan": str, "analysis": str}
    """
    agents = build_agents()

    def emit(stage, content):
        if on_stage:
            on_stage(stage, content)

    plan = _run_single(agents["coordinator"], make_coordination_task(agents["coordinator"], user_requirement))
    emit("协调拆解", plan)

    analysis = _run_single(agents["analyst"], make_analysis_task(agents["analyst"], user_requirement))
    emit("需求分析", analysis)

    return {"plan": plan, "analysis": analysis}


def generate_prd(user_requirement: str, analysis: str, on_stage=None,
                 max_rounds: int = MAX_REVISION_ROUNDS) -> dict:
    """
    阶段二：基于（可能经人工确认/编辑的）需求分析，跑完剩余流程并导出 Word。

    Returns: {"prd_markdown": str, "docx_path": str, "revision_rounds": int,
              "research": str, "evaluation": str, "analysis": str}
    """
    agents = build_agents()

    def emit(stage, content):
        if on_stage:
            on_stage(stage, content)

    # 行业研究
    research = _run_single(agents["researcher"], make_research_task(agents["researcher"], analysis))
    emit("行业研究", research)

    # 技术评估 + 互质疑反馈环
    evaluation = _run_single(agents["evaluator"], make_evaluation_task(agents["evaluator"], analysis, research))
    emit("技术评估", evaluation)

    rounds = 0
    while rounds < max_rounds:
        verdict, feedback = _parse_verdict(evaluation)
        if verdict != "需修订":
            break
        rounds += 1
        emit("互质疑", f"⚠️ 技术评估员提出质疑，退回需求分析师修订（第 {rounds} 轮）：{feedback}")
        analysis = _run_single(agents["analyst"], make_analysis_task(agents["analyst"], user_requirement, feedback))
        emit("需求修订", analysis)
        evaluation = _run_single(agents["evaluator"], make_evaluation_task(agents["evaluator"], analysis, research))
        emit("重新评估", evaluation)

    # 文档汇总
    prd_text = _run_single(agents["writer"], make_documentation_task(agents["writer"], analysis, research, evaluation))
    emit("文档汇总", prd_text)

    # 导出 Word
    safe = re.sub(r"[^\w一-鿿]+", "_", user_requirement[:20]).strip("_")
    docx_path = export_prd_to_docx(prd_text, filename=f"PRD_{safe}_{date.today().isoformat()}.docx")

    return {
        "prd_markdown": prd_text,
        "docx_path": docx_path,
        "revision_rounds": rounds,
        "research": research,
        "evaluation": evaluation,
        "analysis": analysis,
    }


def run_crew(user_requirement: str, on_stage=None) -> dict:
    """一把梭：阶段一 + 阶段二（命令行 / 无人工干预时用）。"""
    a = analyze_requirement(user_requirement, on_stage=on_stage)
    return generate_prd(user_requirement, a["analysis"], on_stage=on_stage)
