"""
性能指标系统 —— 追踪和分析执行性能

特性：
  - 阶段耗时统计
  - Token 消耗统计
  - 性能基准和热点识别
"""
import json
import time
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict, field
from datetime import datetime
from statistics import mean, stdev

logger = logging.getLogger(__name__)


@dataclass
class PhaseDuration:
    """单个阶段的耗时记录"""
    phase: str
    agent: str
    duration_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class PerformanceTracker:
    """性能追踪器"""

    def __init__(self):
        self.phase_durations: List[PhaseDuration] = []
        self.token_usage: Dict[str, int] = {}  # agent -> tokens
        self.session_start_time = time.time()

    def record_phase_duration(self, phase: str, agent: str, duration_seconds: float) -> None:
        """
        记录阶段耗时

        Args:
            phase: 阶段名称
            agent: Agent 名称
            duration_seconds: 耗时（秒）
        """
        record = PhaseDuration(
            phase=phase,
            agent=agent,
            duration_seconds=duration_seconds,
        )
        self.phase_durations.append(record)
        logger.debug(f"[PERF] {phase} ({agent}): {duration_seconds:.2f}s")

    def record_token_usage(self, agent: str, tokens: int) -> None:
        """
        记录 Token 消耗

        Args:
            agent: Agent 名称
            tokens: 消耗的 token 数
        """
        if agent not in self.token_usage:
            self.token_usage[agent] = 0
        self.token_usage[agent] += tokens

    def get_phase_stats(self) -> Dict[str, dict]:
        """
        获取按阶段的统计信息

        Returns:
            {phase_name: {avg_duration, min_duration, max_duration, count}}
        """
        stats = {}
        durations_by_phase = {}

        for record in self.phase_durations:
            phase = record.phase
            if phase not in durations_by_phase:
                durations_by_phase[phase] = []
            durations_by_phase[phase].append(record.duration_seconds)

        for phase, durations in durations_by_phase.items():
            stats[phase] = {
                "count": len(durations),
                "avg_duration": round(mean(durations), 2),
                "min_duration": round(min(durations), 2),
                "max_duration": round(max(durations), 2),
                "stdev": round(stdev(durations), 2) if len(durations) > 1 else 0,
            }

        return stats

    def get_agent_stats(self) -> Dict[str, dict]:
        """
        获取按 Agent 的统计信息

        Returns:
            {agent_name: {phase_count, avg_duration, total_tokens}}
        """
        stats = {}

        # 按 Agent 分组
        durations_by_agent = {}
        for record in self.phase_durations:
            agent = record.agent
            if agent not in durations_by_agent:
                durations_by_agent[agent] = []
            durations_by_agent[agent].append(record.duration_seconds)

        for agent, durations in durations_by_agent.items():
            stats[agent] = {
                "phase_count": len(durations),
                "avg_duration": round(mean(durations), 2),
                "total_duration": round(sum(durations), 2),
                "tokens": self.token_usage.get(agent, 0),
            }

        return stats

    def get_slowest_phases(self, top_n: int = 5) -> List[Dict]:
        """
        获取耗时最长的 N 个阶段

        Args:
            top_n: 返回数量

        Returns:
            按耗时降序排列的阶段列表
        """
        sorted_phases = sorted(
            self.phase_durations,
            key=lambda x: x.duration_seconds,
            reverse=True,
        )
        return [asdict(p) for p in sorted_phases[:top_n]]

    def get_total_duration(self) -> float:
        """获取整个会话的总耗时"""
        return time.time() - self.session_start_time

    def generate_report(self) -> Dict:
        """生成完整的性能报告"""
        return {
            "total_duration_seconds": round(self.get_total_duration(), 2),
            "phase_count": len(self.phase_durations),
            "phase_stats": self.get_phase_stats(),
            "agent_stats": self.get_agent_stats(),
            "slowest_phases": self.get_slowest_phases(top_n=10),
            "token_breakdown": self.token_usage,
        }

    def export_report_json(self, filepath: str) -> None:
        """导出报告为 JSON 文件"""
        report = self.generate_report()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"性能报告已导出：{filepath}")

    def print_summary(self) -> None:
        """打印简洁的性能摘要"""
        report = self.generate_report()
        print("\n" + "=" * 60)
        print("📊 性能报告摘要")
        print("=" * 60)
        print(f"总耗时：{report['total_duration_seconds']}s")
        print(f"阶段数：{report['phase_count']}")

        print("\n🔍 按阶段统计：")
        for phase, stats in report["phase_stats"].items():
            print(f"  {phase}: {stats['avg_duration']}s (共 {stats['count']} 次)")

        print("\n🤖 按 Agent 统计：")
        for agent, stats in report["agent_stats"].items():
            print(f"  {agent}: {stats['total_duration']}s ({stats['phase_count']} 个阶段)")

        print("\n⏱️ 最慢的 3 个阶段：")
        for i, phase in enumerate(report["slowest_phases"][:3], 1):
            print(f"  {i}. {phase['phase']} ({phase['agent']}): {phase['duration_seconds']}s")

        print("=" * 60 + "\n")


# 全局实例
_global_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker() -> PerformanceTracker:
    """获取全局性能追踪器实例"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = PerformanceTracker()
    return _global_tracker


def reset_performance_tracker() -> None:
    """重置全局性能追踪器（用于测试）"""
    global _global_tracker
    _global_tracker = None
