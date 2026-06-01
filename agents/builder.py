"""
Agent 定义层 —— 根据 config 中的角色资料创建 5 个 CrewAI Agent
5 个 Agent 共用同一个 DeepSeek LLM，仅靠 role/goal/backstory 区分身份
"""
from crewai import Agent

from config import AGENT_PROFILES, get_llm
from tools.search_tool import build_search_tool
from tools.rag_tool import build_rag_tool


def build_agents() -> dict:
    """
    创建并返回 5 个 Agent，键为角色 id：
    coordinator / analyst / researcher / evaluator / writer

    阶段 3：给 researcher 绑搜索工具、给 evaluator 绑 RAG 工具
    阶段 4：给 evaluator 开 allow_delegation（互质疑）
    """
    llm = get_llm()

    # 按角色绑定工具：行业研究员→联网搜索；技术评估员→历史经验(RAG)
    role_tools = {
        "researcher": [build_search_tool()],
        "evaluator": [build_rag_tool()],
    }

    agents = {}
    for key, profile in AGENT_PROFILES.items():
        agents[key] = Agent(
            role=profile["role"],
            goal=profile["goal"],
            backstory=profile["backstory"],
            llm=llm,
            tools=role_tools.get(key, []),
            verbose=True,            # 打印 Agent 思考过程，方便调试和演示
            allow_delegation=False,  # 阶段 4 再为技术评估员开启
        )
    return agents
