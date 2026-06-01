"""
通用工具 —— 统一的日志配置等
"""
import logging
import sys


def setup_logger(name: str = "agent-system") -> logging.Logger:
    """返回一个配置好的 logger，输出到控制台，UTF-8 中文友好。"""
    logger = logging.getLogger(name)
    if logger.handlers:  # 避免重复添加 handler
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


logger = setup_logger()
