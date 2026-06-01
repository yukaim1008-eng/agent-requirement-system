"""
Pytest 配置和通用 fixtures
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture(scope="session")
def project_root_path():
    """返回项目根目录路径"""
    return Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def reset_globals():
    """在每个测试前重置全局单例（确保测试隔离）"""
    from core.cost_manager import reset_cost_manager
    from utils.logger import reset_logger
    from utils.cache import get_session_cache
    from utils.metrics import reset_performance_tracker

    reset_cost_manager()
    reset_logger()
    reset_performance_tracker()

    # 清空会话缓存
    cache = get_session_cache()
    cache.clear()

    yield

    # 测试后再次清理
    reset_cost_manager()
    reset_logger()
    reset_performance_tracker()
