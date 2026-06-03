"""
弹性和容错机制 —— 重试、超时、降级

特性：
  - 指数退避重试（指数增长延迟）
  - 超时保护
  - 优雅降级（返回默认内容而不中断流程）
  - 对 API 和 Task 执行的包装
"""
import time
import logging
import asyncio
from functools import wraps
from typing import Callable, Any, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryableError(Exception):
    """可重试的异常（如 API 超时、网络错误）"""
    pass


class NonRetryableError(Exception):
    """不可重试的异常（如参数错误）"""
    pass


def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
) -> T:
    """
    使用指数退避算法重试函数

    Args:
        func: 要重试的函数
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 指数增长因子
        max_delay: 最大延迟（秒）

    Returns:
        函数执行结果

    Raises:
        如果所有重试都失败，抛出最后一个异常
    """
    last_exception = None
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            return func()
        except NonRetryableError:
            raise  # 不可重试的异常直接抛出
        except RetryableError as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"[RETRY] 第 {attempt + 1} 次尝试失败，{delay:.1f}s 后重试：{str(e)[:100]}")
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(f"[RETRY] 失败，已达最大重试次数 {max_retries}")
        except Exception as e:
            # 其他异常当作可重试处理
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"[RETRY] 第 {attempt + 1} 次尝试异常，{delay:.1f}s 后重试：{str(e)[:100]}")
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(f"[RETRY] 异常，已达最大重试次数 {max_retries}")

    if last_exception:
        raise last_exception


def retry_decorator(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
):
    """
    装饰器：为函数添加重试能力

    Example:
        @retry_decorator(max_retries=3)
        def api_call():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return retry_with_backoff(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                initial_delay=initial_delay,
                backoff_factor=backoff_factor,
            )
        return wrapper
    return decorator


def safe_run_crew(
    func: Callable[..., str],
    timeout: float = 600.0,
    fallback: str = "",
    operation_name: str = "operation",
) -> str:
    """
    安全执行 Crew Task 的包装函数

    - 添加超时保护
    - 返回降级内容（而不中断流程）
    - 记录异常

    Args:
        func: 要执行的 Crew 任务函数（应返回字符串）
        timeout: 超时时间（秒）
        fallback: 超时/异常时的降级内容
        operation_name: 操作名称（用于日志）

    Returns:
        函数结果，或者降级内容（如果失败）
    """
    import signal

    class TimeoutException(Exception):
        pass

    def timeout_handler(signum, frame):
        raise TimeoutException(f"操作超时（{timeout}s）")

    # Windows 不支持 signal，改用其他方式处理超时
    try:
        if hasattr(signal, "SIGALRM"):
            # POSIX 系统（Linux/Mac）
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout))
        try:
            result = func()
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)  # 取消闹钟
            return result
        except TimeoutException:
            logger.error(f"[TIMEOUT] {operation_name} 超时（{timeout}s），采用降级方案")
            return fallback
    except Exception as e:
        logger.error(f"[FALLBACK] {operation_name} 异常：{str(e)[:200]}")
        return fallback


# 连接中断类异常 —— 这些错误重试无效（对方已经 RST / 拒绝），应快速失败
_CONNECTION_FATAL_ERRORS = (
    ConnectionResetError,    # [WinError 10054] 远程主机强迫关闭连接
    ConnectionRefusedError,  # 对方端口拒绝
    ConnectionAbortedError,  # 连接被中止
    BrokenPipeError,         # 管道断裂
    TimeoutError,            # 连接超时（不同于我们自己的超时）
)

def safe_run_with_timeout(
    func: Callable[..., str],
    timeout_seconds: float = 600.0,
    fallback: str = "",
    operation_name: str = "operation",
) -> str:
    """
    使用多线程实现跨平台的超时保护。

    关键改进：
      - ConnectionResetError 等连接中断类异常 → 快速失败（不等超时），直接降级
      - 线程在超时后不会被 join() 无限阻塞（daemon 线程主进程退出时自动回收）

    Args:
        func: 要执行的函数
        timeout_seconds: 超时时间
        fallback: 降级内容
        operation_name: 操作名称

    Returns:
        函数结果或降级内容
    """
    import threading

    result_holder = {"value": fallback}
    exception_holder = {"error": None}
    # 缩短的连接探测间隔：每 5 秒检查一次线程是否已死 / 是否遇到连接中断
    _POLL_INTERVAL = 5.0

    def run_in_thread():
        try:
            result_holder["value"] = func()
        except _CONNECTION_FATAL_ERRORS as e:
            # 连接中断 → 打标记让主线程快速感知，不走完整超时
            exception_holder["error"] = e
            logger.warning(f"[CONNECTION-FATAL] {operation_name} 连接被远端中断：{e}")
        except Exception as e:
            exception_holder["error"] = e

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()

    # 分段 join：每 _POLL_INTERVAL 检查一次，连接中断时立即退出，不傻等 timeout_seconds
    elapsed = 0.0
    while elapsed < timeout_seconds:
        thread.join(timeout=_POLL_INTERVAL)
        if not thread.is_alive():
            break  # 线程已结束，正常 / 异常都立即处理
        if exception_holder["error"] is not None and isinstance(exception_holder["error"], _CONNECTION_FATAL_ERRORS):
            # 连接已死，线程可能还在 futile retry → 不等了，直接降级
            logger.error(f"[FAST-FAIL] {operation_name} 连接中断，不等超时直接降级（已等待 {elapsed:.0f}s）")
            return fallback
        elapsed += _POLL_INTERVAL

    if thread.is_alive():
        logger.error(f"[TIMEOUT] {operation_name} 超时（{timeout_seconds}s），采用降级方案")
        return fallback

    if exception_holder["error"]:
        logger.error(f"[FALLBACK] {operation_name} 异常：{str(exception_holder['error'])[:200]}")
        return fallback

    return result_holder["value"]


# 重试策略预设
RETRY_STRATEGIES = {
    "aggressive": {"max_retries": 5, "initial_delay": 0.5, "backoff_factor": 1.5},
    "moderate": {"max_retries": 3, "initial_delay": 1.0, "backoff_factor": 2.0},
    "conservative": {"max_retries": 1, "initial_delay": 2.0, "backoff_factor": 2.0},
}


def get_retry_strategy(strategy_name: str = "moderate") -> dict:
    """获取预定义的重试策略"""
    return RETRY_STRATEGIES.get(strategy_name, RETRY_STRATEGIES["moderate"])
