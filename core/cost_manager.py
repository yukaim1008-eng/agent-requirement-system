"""
成本管理器 —— 追踪 Token 消耗、估算费用、防止超支

特性：
  - 实时 Token 计数（基于 Tiktoken）
  - 会话级费用估算
  - 预算告警与强制中止
  - 按 Agent 分类统计
"""
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """单次 API 调用的 Token 消耗记录"""
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    timestamp: str
    cost_usd: float

    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class CostManager:
    """
    Token 消耗与成本管理。

    DeepSeek 定价（参考）：
      - 输入：¥0.14/百万 token ≈ $0.020/百万 token
      - 输出：¥0.28/百万 token ≈ $0.040/百万 token
    """

    # DeepSeek 官方定价（USD 每百万 token）
    DEEPSEEK_INPUT_COST_PER_1M = 0.020
    DEEPSEEK_OUTPUT_COST_PER_1M = 0.040

    def __init__(self, max_session_tokens: int = 100000, max_session_budget_usd: float = 5.0):
        """
        初始化成本管理器

        Args:
            max_session_tokens: 单个会话的最大 token 数
            max_session_budget_usd: 单个会话的最大预算（美元）
        """
        self.max_session_tokens = max_session_tokens
        self.max_session_budget_usd = max_session_budget_usd

        self.usages: list[TokenUsage] = []
        self.session_start_time = datetime.now().isoformat()

    def record_usage(self, agent: str, model: str, input_tokens: int, output_tokens: int) -> TokenUsage:
        """
        记录一次 API 调用的 Token 消耗

        Args:
            agent: Agent 名称
            model: 模型名称
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数

        Returns:
            TokenUsage 对象
        """
        cost = self._estimate_cost(input_tokens, output_tokens)
        usage = TokenUsage(
            agent=agent,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            timestamp=datetime.now().isoformat(),
            cost_usd=cost
        )
        self.usages.append(usage)

        logger.info(f"[COST] {agent}: {input_tokens} in + {output_tokens} out = ${cost:.4f}")
        return usage

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """计算 API 调用成本（USD）"""
        return (
            (input_tokens / 1_000_000) * self.DEEPSEEK_INPUT_COST_PER_1M +
            (output_tokens / 1_000_000) * self.DEEPSEEK_OUTPUT_COST_PER_1M
        )

    def total_tokens_used(self) -> int:
        """返回本会话累计 Token 数"""
        return sum(u.total_tokens() for u in self.usages)

    def total_cost_usd(self) -> float:
        """返回本会话累计成本（USD）"""
        return sum(u.cost_usd for u in self.usages)

    def check_budget(self, threshold: float = 0.8) -> tuple[bool, Dict]:
        """
        检查是否接近或超过预算

        Args:
            threshold: 告警阈值（0.8 表示 80% 时告警）

        Returns:
            (is_ok, report_dict)：
              - is_ok: True 表示未超限，False 表示已超限或接近
              - report_dict: 包含消耗详情
        """
        total_tokens = self.total_tokens_used()
        total_cost = self.total_cost_usd()
        tokens_used_percent = total_tokens / self.max_session_tokens
        cost_used_percent = total_cost / self.max_session_budget_usd

        report = {
            "tokens_used": total_tokens,
            "tokens_limit": self.max_session_tokens,
            "tokens_used_percent": round(tokens_used_percent * 100, 1),
            "cost_usd": round(total_cost, 4),
            "cost_limit_usd": self.max_session_budget_usd,
            "cost_used_percent": round(cost_used_percent * 100, 1),
        }

        # 判断是否超限或接近告警
        is_ok = (tokens_used_percent < threshold) and (cost_used_percent < threshold)

        if tokens_used_percent >= threshold:
            logger.warning(f"[BUDGET] Token 告警：{report['tokens_used']} / {report['tokens_limit']}")

        if cost_used_percent >= threshold:
            logger.warning(f"[BUDGET] Cost 告警：${report['cost_usd']} / ${report['cost_limit_usd']}")

        return is_ok, report

    def enforce_budget(self) -> None:
        """
        检查是否超预算，超则抛异常

        Raises:
            BudgetExceededError
        """
        is_ok, report = self.check_budget(threshold=1.0)
        if not is_ok:
            raise BudgetExceededError(
                f"会话超预算：{report['cost_usd']} USD > {report['cost_limit_usd']} USD"
            )

    def generate_report(self) -> Dict:
        """生成成本统计报告"""
        agent_costs = {}
        for usage in self.usages:
            if usage.agent not in agent_costs:
                agent_costs[usage.agent] = {"tokens": 0, "cost": 0.0, "calls": 0}
            agent_costs[usage.agent]["tokens"] += usage.total_tokens()
            agent_costs[usage.agent]["cost"] += usage.cost_usd
            agent_costs[usage.agent]["calls"] += 1

        return {
            "session_start": self.session_start_time,
            "session_end": datetime.now().isoformat(),
            "total_tokens": self.total_tokens_used(),
            "total_cost_usd": round(self.total_cost_usd(), 4),
            "agent_breakdown": {
                agent: {
                    "tokens": data["tokens"],
                    "cost_usd": round(data["cost"], 4),
                    "calls": data["calls"],
                }
                for agent, data in agent_costs.items()
            },
            "usage_log": [asdict(u) for u in self.usages],
        }

    def export_report_json(self, filepath: str) -> None:
        """导出报告为 JSON 文件"""
        report = self.generate_report()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"成本报告已导出：{filepath}")


class BudgetExceededError(Exception):
    """预算超限异常"""
    pass


# 全局单例（方便跨模块访问）
_global_cost_manager: Optional[CostManager] = None


def get_cost_manager() -> CostManager:
    """获取全局成本管理器实例"""
    global _global_cost_manager
    if _global_cost_manager is None:
        _global_cost_manager = CostManager()
    return _global_cost_manager


def reset_cost_manager() -> None:
    """重置全局成本管理器（用于测试）"""
    global _global_cost_manager
    _global_cost_manager = None
