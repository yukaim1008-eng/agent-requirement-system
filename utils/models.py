"""
数据模型 —— 标准化 Agent 输出格式

使用 dataclass 定义结构，便于 JSON 序列化和字段验证
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from enum import Enum
import json


class FeasibilityStatus(str, Enum):
    """可行性状态"""
    FEASIBLE = "feasible"                 # 可行
    NEEDS_REVISION = "needs_revision"     # 需修订
    NOT_FEASIBLE = "not_feasible"         # 不可行


class PriorityLevel(str, Enum):
    """优先级"""
    CRITICAL = "critical"                 # 关键
    HIGH = "high"                         # 高
    MEDIUM = "medium"                     # 中
    LOW = "low"                           # 低


@dataclass
class UserStory:
    """用户故事"""
    role: str                             # "作为<角色>"
    feature: str                          # "我想要<功能>"
    value: str                            # "以便<价值>"
    priority: PriorityLevel = PriorityLevel.MEDIUM
    acceptance_criteria: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典，用于 JSON 序列化"""
        data = asdict(self)
        data['priority'] = self.priority.value
        return data


@dataclass
class CompetitorAnalysis:
    """竞品分析"""
    name: str                             # 竞品名称
    strengths: List[str] = field(default_factory=list)      # 优势
    weaknesses: List[str] = field(default_factory=list)     # 劣势
    market_position: str = ""             # 市场定位
    url: str = ""                         # 产品链接
    notes: str = ""                       # 备注

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RiskAssessment:
    """风险评估"""
    risk_name: str                        # 风险名称
    severity: str = "medium"              # 严重程度：critical/high/medium/low
    mitigation: str = ""                  # 缓解措施
    owner: str = ""                       # 负责人


@dataclass
class TechEvaluation:
    """技术评估报告"""
    feasibility: FeasibilityStatus = FeasibilityStatus.FEASIBLE
    recommendation: str = ""              # 建议
    risks: List[RiskAssessment] = field(default_factory=list)
    estimated_effort: str = ""            # 工作量估计，e.g. "2-3 weeks"
    recommended_stack: str = ""           # 推荐技术栈
    implementation_notes: str = ""        # 实现备注

    def to_dict(self) -> dict:
        data = asdict(self)
        data['feasibility'] = self.feasibility.value
        data['risks'] = [asdict(r) for r in self.risks]
        return data


@dataclass
class PRDSection:
    """PRD 的标准章节"""
    title: str
    content: str
    subsections: List['PRDSection'] = field(default_factory=list)

    def to_markdown(self, level: int = 1) -> str:
        """转换为 Markdown"""
        md = f"{'#' * level} {self.title}\n\n{self.content}\n\n"
        for subsection in self.subsections:
            md += subsection.to_markdown(level + 1)
        return md


@dataclass
class ProjectMetadata:
    """项目元数据"""
    requirement: str                      # 原始需求
    created_at: str                       # 创建时间
    model: str = "deepseek-chat"          # 使用的模型
    revision_rounds: int = 0              # 修订轮数
    total_tokens: int = 0                 # 消耗的 token 数
    execution_time_seconds: float = 0.0   # 执行时间

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PRDDocument:
    """完整的 PRD 文档"""
    metadata: ProjectMetadata
    sections: List[PRDSection]
    requirements: List[UserStory] = field(default_factory=list)
    competitors: List[CompetitorAnalysis] = field(default_factory=list)
    tech_evaluation: Optional[TechEvaluation] = None

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        data = {
            "metadata": self.metadata.to_dict(),
            "sections": [{"title": s.title, "content": s.content} for s in self.sections],
            "requirements": [r.to_dict() for r in self.requirements],
            "competitors": [c.to_dict() for c in self.competitors],
            "tech_evaluation": self.tech_evaluation.to_dict() if self.tech_evaluation else None,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        """转换为 Markdown"""
        md = f"# 需求规格说明书（PRD）\n\n"
        md += f"**创建时间**：{self.metadata.created_at}\n\n"

        for section in self.sections:
            md += section.to_markdown()

        return md


# 输出格式验证辅助函数
def validate_user_stories(stories: List[UserStory]) -> tuple[bool, str]:
    """验证用户故事的完整性"""
    if not stories:
        return False, "没有用户故事"

    for i, story in enumerate(stories):
        if not story.role or not story.feature or not story.value:
            return False, f"用户故事 {i+1} 缺少必要字段"

    return True, ""


def validate_tech_evaluation(evaluation: TechEvaluation) -> tuple[bool, str]:
    """验证技术评估的完整性"""
    if not evaluation.recommendation:
        return False, "缺少建议"

    if evaluation.feasibility == FeasibilityStatus.NOT_FEASIBLE and not evaluation.recommendation:
        return False, "不可行时必须提供建议"

    return True, ""
