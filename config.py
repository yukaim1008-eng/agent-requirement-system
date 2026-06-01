"""
集中配置 —— API Key、模型、5 个 Agent 的角色提示词都从这里读
所有模块统一从 config 导入，避免硬编码散落各处
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 始终从 config.py 所在目录加载 .env，不依赖运行时的工作目录
load_dotenv(Path(__file__).parent / ".env")

# ==================== API 密钥与路径 ====================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")          # 留空则行业研究员降级为 LLM 模拟
RAG_DIR = os.getenv("RAG_DIR", "")                        # RAG 项目目录（技术评估员联动用）
RAG_PYTHON = os.getenv("RAG_PYTHON", "")                  # RAG 项目自己的 venv python

# ==================== 模型配置 ====================
# CrewAI 底层用 LiteLLM 调模型，DeepSeek 的写法是 "deepseek/deepseek-chat"
DEEPSEEK_MODEL = "deepseek/deepseek-chat"
LLM_TEMPERATURE = 0.3      # 需求分析需要一点发散，但别太高
LLM_MAX_TOKENS = 4096

# ==================== 互质疑 / 多轮修订配置 ====================
MAX_REVISION_ROUNDS = 1    # 技术评估员打回后，需求分析师最多修订几轮（防止无限循环）

# ==================== 成本控制 ====================
MAX_SESSION_TOKENS = 100000          # 单个会话最大 Token 数
MAX_SESSION_BUDGET_USD = 5.0         # 单个会话最大预算（美元）
COST_WARNING_THRESHOLD = 0.8         # 预算告警阈值（80% 时告警）

# ==================== 超时保护 ====================
TASK_TIMEOUT_SECONDS = 600           # 单个 Task 的超时时间（秒）
MAX_REVISION_TASK_TIMEOUT = 300      # 互质疑修订任务的超时（秒，更短）

# ==================== 缓存策略 ====================
CACHE_TTL_SECONDS = 86400            # 缓存有效期（24h）
ENABLE_CACHE = True                  # 是否启用缓存

# ==================== 日志配置 ====================
LOG_LEVEL = "INFO"                   # 日志级别：DEBUG / INFO / WARNING / ERROR
ENABLE_STRUCTURED_LOGGING = True     # 是否输出结构化日志（JSON）

# ==================== 5 个 Agent 角色定义 ====================
# CrewAI 的 Agent 用 role/goal/backstory 三段式描述身份，集中放这里便于调优
AGENT_PROFILES = {
    "coordinator": {
        "role": "需求分析项目协调员",
        "goal": "把用户的原始需求拆解成子任务，按逻辑调度各专家 Agent，最终整合出完整、专业的需求规格说明书",
        "backstory": "你是一位经验丰富的 IT 项目经理，擅长把一句模糊需求拆解成可执行的子任务，"
                     "协调需求、研究、技术团队分工，并把控最终交付质量。",
    },
    "analyst": {
        "role": "需求分析师",
        "goal": "深挖用户需求，输出清晰的功能需求清单和标准用户故事（User Story）",
        "backstory": "你是资深需求分析师，擅长从一句话需求中识别核心诉求、补全被忽略的场景，"
                     "并用标准格式表达用户故事（作为<角色>，我想要<功能>，以便<价值>）。"
                     "当技术评估员指出某需求不可行或风险过高时，你能据此调整需求。",
    },
    "researcher": {
        "role": "行业研究员",
        "goal": "调研同类产品、竞品和行业合规要求，提炼出对本需求有参考价值的关键信息",
        "backstory": "你是行业分析师，擅长快速检索并提炼市场信息。你会使用联网搜索工具获取真实资料，"
                     "基于事实总结，绝不凭空编造竞品或数据。",
    },
    "evaluator": {
        "role": "技术评估员",
        "goal": "评估每个需求点的技术可行性、风险和工作量，给出建议技术栈、架构约束和工期预估",
        "backstory": "你是资深技术架构师。你会从实现角度审视每条需求，必要时查询历史项目知识库参考过往经验。"
                     "当某需求时间紧、风险高、明显不可行时，你会主动向需求分析师提出简化或调整建议。",
    },
    "writer": {
        "role": "文档专员",
        "goal": "汇总所有前序产出，整理成结构清晰、专业规范的需求规格说明书（PRD）",
        "backstory": "你是技术文档专家，擅长把零散信息组织成专业文档。你产出的 PRD 必须包含："
                     "项目背景、功能需求清单、用户故事、竞品分析摘要、技术可行性评估与建议。",
    },
}


# ==================== LLM 工厂 ====================
def get_llm():
    """返回配置好的 CrewAI LLM 实例（DeepSeek）。5 个 Agent 共用同一个实例。"""
    from crewai import LLM
    return LLM(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )


# ==================== 启动校验 ====================
def validate_config():
    """启动时检查必要配置，缺失则给出明确的中文提示"""
    if not DEEPSEEK_API_KEY or "your-" in DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY 缺失，请在 .env 文件中配置")
    if not TAVILY_API_KEY:
        print("[提示] 未配置 TAVILY_API_KEY，行业研究员将降级为 LLM 模拟搜索")
    if not RAG_DIR or not RAG_PYTHON:
        print("[提示] 未配置 RAG 路径，技术评估员的历史经验查询将不可用（不影响主流程）")
