"""
联网搜索工具 —— 行业研究员用
降级设计：配了 TAVILY_API_KEY 走真实 Tavily 搜索；没配则用 DeepSeek 模拟兜底
"""
from crewai.tools import tool

from config import TAVILY_API_KEY, DEEPSEEK_API_KEY


@tool("web_search")
def search_web(query: str) -> str:
    """
    行业竞品联网搜索：搜索互联网，获取竞品、同类产品、行业趋势或合规信息。
    输入：一个搜索查询词（字符串）。返回：搜索结果摘要。
    （工具名必须为 ASCII —— OpenAI 兼容接口要求函数名只能含字母/数字/_/-）
    """
    if TAVILY_API_KEY:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=TAVILY_API_KEY)
            resp = client.search(query=query, max_results=5, search_depth="basic")
            results = resp.get("results", [])
            if not results:
                return f"未搜索到关于「{query}」的结果。"
            lines = [f"针对「{query}」的联网搜索结果（来源：Tavily）："]
            for i, r in enumerate(results, 1):
                title = r.get("title", "")
                content = r.get("content", "")[:300]
                url = r.get("url", "")
                lines.append(f"{i}. {title}\n   {content}\n   来源：{url}")
            return "\n".join(lines)
        except Exception as e:
            return f"[Tavily 搜索异常，降级处理] {e}"
    # 未配置 Tavily key → LLM 模拟兜底
    return _simulate_search(query)


def _simulate_search(query: str) -> str:
    """无 Tavily key 时的降级：让 DeepSeek 基于训练知识给出参考（明确标注非实时）。"""
    try:
        from langchain_deepseek import ChatDeepSeek
        llm = ChatDeepSeek(
            model="deepseek-chat", api_key=DEEPSEEK_API_KEY,
            temperature=0.3, max_tokens=800,
        )
        prompt = (
            f"请基于你的知识，就以下查询给出简要的竞品 / 行业参考信息（3-5 点）：\n"
            f"「{query}」\n"
            "请在开头注明这是基于模型知识的参考、非实时搜索结果。"
        )
        resp = llm.invoke(prompt)
        return resp.content.strip()
    except Exception as e:
        return f"[未配置 Tavily 且模拟失败：{e}] 请基于你的行业知识进行分析。"


def build_search_tool():
    """返回配置好的搜索工具（供 agents 绑定）。"""
    return search_web
