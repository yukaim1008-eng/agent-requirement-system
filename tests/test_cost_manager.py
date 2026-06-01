"""
测试成本管理模块
"""
import pytest
from core.cost_manager import CostManager, BudgetExceededError


class TestCostManager:
    """测试成本管理器"""

    def test_initialization(self):
        """测试初始化"""
        cm = CostManager(max_session_tokens=50000, max_session_budget_usd=5.0)
        assert cm.max_session_tokens == 50000
        assert cm.max_session_budget_usd == 5.0
        assert cm.total_tokens_used() == 0
        assert cm.total_cost_usd() == 0

    def test_record_usage(self):
        """测试记录 Token 消耗"""
        cm = CostManager()
        usage = cm.record_usage("analyst", "deepseek-chat", 100, 50)

        assert usage.agent == "analyst"
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cost_usd > 0
        assert cm.total_tokens_used() == 150

    def test_multiple_agents_tracking(self):
        """测试多 Agent 追踪"""
        cm = CostManager()
        cm.record_usage("analyst", "deepseek-chat", 100, 50)
        cm.record_usage("researcher", "deepseek-chat", 200, 100)

        assert cm.total_tokens_used() == 450  # 100+50+200+100

        report = cm.generate_report()
        assert "analyst" in report["agent_breakdown"]
        assert "researcher" in report["agent_breakdown"]

    def test_budget_check_under_limit(self):
        """测试预算检查：未超限"""
        cm = CostManager(max_session_budget_usd=10.0)
        cm.record_usage("agent", "model", 100, 50)  # 很小的消耗

        is_ok, report = cm.check_budget(threshold=0.8)
        assert is_ok
        assert report["cost_used_percent"] < 80

    def test_budget_check_over_threshold(self):
        """测试预算检查：超过告警阈值"""
        cm = CostManager(max_session_budget_usd=0.1, max_session_tokens=10000)
        # 消耗足以超过 80% 的预算
        cm.record_usage("agent", "model", 5000, 5000)

        is_ok, report = cm.check_budget(threshold=0.8)
        # 应该超过 80% 的告警阈值（tokens 或 cost）
        assert report["tokens_used_percent"] > 80 or report["cost_used_percent"] > 80

    def test_enforce_budget_raises_when_exceeded(self):
        """测试强制预算：超出时抛异常"""
        cm = CostManager(max_session_budget_usd=0.01)  # 非常低的预算

        # 这会导致成本超出预算
        for _ in range(10):
            cm.record_usage("agent", "model", 50000, 50000)

        with pytest.raises(BudgetExceededError):
            cm.enforce_budget()

    def test_cost_calculation(self):
        """测试成本计算"""
        cm = CostManager()
        # DeepSeek 定价：input $0.020/1M, output $0.040/1M
        # 1000 input + 1000 output = $0.020 * 0.001 + $0.040 * 0.001 = $0.00006
        usage = cm.record_usage("agent", "model", 1000, 1000)
        expected_cost = (1000 / 1_000_000) * 0.020 + (1000 / 1_000_000) * 0.040
        assert abs(usage.cost_usd - expected_cost) < 0.0001

    def test_generate_report(self):
        """测试报告生成"""
        cm = CostManager()
        # 使用更大的 token 数以获得可检测的成本
        cm.record_usage("analyst", "deepseek-chat", 100000, 50000)
        cm.record_usage("researcher", "deepseek-chat", 200000, 100000)

        report = cm.generate_report()

        assert report["total_tokens"] == 450000
        assert report["total_cost_usd"] > 0
        assert "analyst" in report["agent_breakdown"]
        assert "researcher" in report["agent_breakdown"]
        assert "usage_log" in report
