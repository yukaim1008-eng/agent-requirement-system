"""
测试公网 demo 的访问口令门控 —— 核心是那个口令比较函数。

为什么要测它：这是"防刷"的唯一一道闸。比较逻辑要是写错（比如把
"" 也判成通过、或前缀匹配），整道闸就形同虚设。所以哪怕只有一行，也钉死它。
"""
from utils.auth import password_matches


class TestPasswordMatches:
    """口令必须完全一致才放行；空口令一律拒绝。"""

    def test_exact_match_grants(self):
        assert password_matches("demo-2026", "demo-2026") is True

    def test_wrong_password_rejected(self):
        assert password_matches("wrong", "demo-2026") is False

    def test_prefix_does_not_match(self):
        # 防止"前缀也算过"这种低级漏洞
        assert password_matches("demo", "demo-2026") is False

    def test_empty_entered_rejected(self):
        assert password_matches("", "demo-2026") is False

    def test_empty_configured_rejected(self):
        # 万一线上忘了配口令，也不能因为用户也留空就放行
        assert password_matches("", "") is False
        assert password_matches("demo-2026", "") is False
