"""
输入验证和边界检查 —— 防止 Prompt Injection 和异常输入

特性：
  - 长度限制
  - 字符清理
  - 黑名单关键词检查
  - Prompt Injection 检测
"""
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# 可疑的 Prompt Injection 关键词（中英文混合）
INJECTION_KEYWORDS = [
    "ignore", "忽略", "不要", "别管", "以下命令", "系统提示",
    "重新开始", "重置", "disregard", "instructions", "system prompt",
    "override", "bypass", "forget", "previous"
]

# 不应该出现的控制字符
DANGEROUS_CHARS = r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]'


def sanitize_input(text: str) -> str:
    """
    清理输入文本

    - 删除控制字符
    - 规范化空白
    """
    # 删除控制字符
    text = re.sub(DANGEROUS_CHARS, '', text)
    # 规范化空白（多个空格/换行变为单个）
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def validate_requirement_length(text: str, min_len: int = 10, max_len: int = 5000) -> Tuple[bool, str]:
    """
    检查需求长度

    Args:
        text: 需求文本
        min_len: 最小长度
        max_len: 最大长度

    Returns:
        (is_valid, error_message)
    """
    text = text.strip()
    if len(text) < min_len:
        return False, f"需求过短（最少 {min_len} 个字符，当前 {len(text)} 个）"
    if len(text) > max_len:
        return False, f"需求过长（最多 {max_len} 个字符，当前 {len(text)} 个）"
    return True, ""


def detect_injection_keywords(text: str) -> Tuple[bool, list]:
    """
    检测可疑的 Prompt Injection 关键词

    Args:
        text: 需求文本

    Returns:
        (has_injection, found_keywords)
    """
    text_lower = text.lower()
    found = []

    for keyword in INJECTION_KEYWORDS:
        # 对中文关键词和英文关键词分别处理
        if '一' <= keyword[0] <= '鿿':
            # 中文关键词，不使用 \b（中文没有单词边界）
            if keyword in text_lower:
                found.append(keyword)
        else:
            # 英文关键词，使用单词边界
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                found.append(keyword)

    return len(found) > 0, found


def validate_requirement(
    text: str,
    min_len: int = 10,
    max_len: int = 5000,
    check_injection: bool = True,
) -> Tuple[bool, str]:
    """
    全面验证需求文本

    Args:
        text: 需求文本
        min_len: 最小长度
        max_len: 最大长度
        check_injection: 是否检查 Prompt Injection

    Returns:
        (is_valid, error_message)
    """
    if not text:
        return False, "需求文本不能为空"

    # 清理输入
    text = sanitize_input(text)

    # 检查长度
    is_valid, error = validate_requirement_length(text, min_len, max_len)
    if not is_valid:
        return False, error

    # 检查 Prompt Injection
    if check_injection:
        has_injection, keywords = detect_injection_keywords(text)
        if has_injection:
            logger.warning(f"[INJECTION] 检测到可疑关键词：{keywords}")
            return False, f"输入包含可疑关键词：{', '.join(keywords)}"

    logger.info(f"[VALIDATE] 需求验证通过：{len(text)} 个字符")
    return True, ""


def split_requirement_into_sentences(text: str) -> list:
    """
    将需求文本按句子分割

    用于后续的需求分解和分析
    """
    # 按中文句号、英文句号、感叹号、问号分割
    sentences = re.split(r'[。.!！?？\n]+', text)
    # 过滤空白句子
    return [s.strip() for s in sentences if s.strip()]


def extract_keywords_from_requirement(text: str, top_n: int = 5) -> list:
    """
    从需求文本中提取关键词

    简单实现：以名词和动词为主
    """
    # 这是一个简化的实现，实际可以用 jieba 等中文分词库
    # 当前只是基于长度和频率的启发式方法
    words = re.findall(r'[一-鿿]+|[a-zA-Z]+', text)

    # 过滤太短的词
    words = [w for w in words if len(w) >= 2]

    # 统计频率
    from collections import Counter
    word_freq = Counter(words)

    # 返回频率最高的 N 个
    return [word for word, _ in word_freq.most_common(top_n)]
