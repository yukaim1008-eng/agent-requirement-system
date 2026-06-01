"""
轻量访问门控 —— 给公网 demo 加一道共享口令，防止付费 API 成本被刷。

这里只放纯逻辑（口令比较），不依赖 Streamlit，方便单测。
读取口令配置 + 输入框 UI 放在 main.py（属于界面层）。
"""
import hmac


def password_matches(entered: str, configured: str) -> bool:
    """判断用户输入的口令是否与配置的口令完全一致。

    用 hmac.compare_digest 做常量时间比较，避免计时侧信道攻击
    —— 普通的 == 逐字符比较会在第一个不同处提前返回，攻击者据此
    能逐位试出口令对了几位。compare_digest 无论对错都跑满全程。

    空口令一律拒绝：避免线上忘配口令时、用户也留空就被放行。
    """
    if not entered or not configured:
        return False
    return hmac.compare_digest(str(entered), str(configured))
