"""
集成测试 —— 验证多 Agent 编排真的把 token 用量记进了成本管理器。

为什么单独建这个文件？
  test_cost_manager.py 测的是 CostManager 这个「类」本身（孤立地调 record_usage），
  它一直是绿的 —— 但它测不到「真实流程里到底有没有人去调 record_usage」。
  这个文件补的就是那一层：_run_single 跑完后，成本有没有被真正记下来。
  （这正是之前的 bug：crew_runner 里 str(crew.kickoff()) 把带 token_usage 的对象扔了。）
"""
import pytest

import core.crew_runner as crew_runner
from core.cost_manager import CostManager, BudgetExceededError


# ============ 用最小的「替身」模拟 CrewAI 的返回，避免真实 API 调用 ============
class _FakeUsage:
    """模拟 crewai 的 UsageMetrics（只保留我们要用的字段）"""
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class _FakeCrewOutput:
    """模拟 crew.kickoff() 的真实返回值 CrewOutput"""
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.token_usage = _FakeUsage(prompt_tokens, completion_tokens)

    def __str__(self) -> str:
        return "假的 PRD 文本产出"


class _FakeCrew:
    """替身 Crew：构造时吞掉所有参数，kickoff() 返回固定的假产出"""
    def __init__(self, *args, **kwargs):
        pass

    def kickoff(self):
        return _FakeCrewOutput(prompt_tokens=1000, completion_tokens=500)


class _FakeAgent:
    role = "需求分析师"


class _FakeTask:
    description = "分析校园二手交易小程序的需求"


class TestCostWiring:
    """_run_single 必须把真实 token 用量接进成本管理器"""

    def test_run_single_records_token_usage(self, monkeypatch):
        # 用替身换掉真正的 Crew，避免真实联网/计费
        monkeypatch.setattr(crew_runner, "Crew", _FakeCrew)

        cm = CostManager()
        result = crew_runner._run_single(_FakeAgent(), _FakeTask(), cost_mgr=cm)

        # 文本产出仍要正常返回
        assert result == "假的 PRD 文本产出"
        # 关键断言：1000 + 500 的 token 必须被真正记下来（旧代码这里永远是 0）
        assert cm.total_tokens_used() == 1500
        assert cm.total_cost_usd() > 0

    def test_run_single_enforces_budget_when_exceeded(self, monkeypatch):
        """超预算时，_run_single 必须抛 BudgetExceededError —— 把"强制停止"真正接上。

        旧代码只 check_budget()（记日志、从不抛），所以这条会失败，
        正好证明"强制停止"根本没接线。"""
        monkeypatch.setattr(crew_runner, "Crew", _FakeCrew)  # 每次产生 1000+500 token
        cm = CostManager(max_session_tokens=100, max_session_budget_usd=5.0)  # 1500 > 100，超 token 上限
        with pytest.raises(BudgetExceededError):
            crew_runner._run_single(_FakeAgent(), _FakeTask(), cost_mgr=cm)
