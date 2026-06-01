"""
结构化日志系统 —— 支持 JSON 格式输出便于分析

特性：
  - 自动记录时间戳、操作名、耗时
  - JSON 结构化输出
  - 按 Agent 分类统计
"""
import json
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict, field


@dataclass
class PhaseLog:
    """阶段执行日志"""
    phase: str
    agent: str
    status: str  # PENDING / RUNNING / SUCCESS / FAILED / TIMEOUT
    start_time: str
    end_time: str = ""
    duration_seconds: float = 0.0
    tokens_used: int = 0
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json_line(self) -> str:
        """转换为 JSON 行"""
        return json.dumps(asdict(self), ensure_ascii=False)


class StructuredLogger:
    """结构化日志记录器"""

    def __init__(self, name: str = "crew-runner", enable_json: bool = True):
        self.name = name
        self.enable_json = enable_json
        self.logs: list[PhaseLog] = []
        self.phase_timers: Dict[str, float] = {}

        # 配置标准 logger
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def start_phase(self, phase: str, agent: str) -> None:
        """记录阶段开始"""
        self.phase_timers[phase] = time.time()
        self.logger.info(f"[START] {phase} by {agent}")

    def end_phase(
        self,
        phase: str,
        agent: str,
        status: str = "SUCCESS",
        tokens_used: int = 0,
        error_message: str = "",
        **metadata
    ) -> PhaseLog:
        """
        记录阶段结束

        Args:
            phase: 阶段名称
            agent: Agent 名称
            status: 状态（SUCCESS / FAILED / TIMEOUT）
            tokens_used: 本阶段消耗的 token 数
            error_message: 错误信息（如有）
            **metadata: 额外元数据
        """
        duration = 0.0
        if phase in self.phase_timers:
            duration = time.time() - self.phase_timers[phase]

        log_entry = PhaseLog(
            phase=phase,
            agent=agent,
            status=status,
            start_time=datetime.now().isoformat(),
            duration_seconds=round(duration, 2),
            tokens_used=tokens_used,
            error_message=error_message,
            metadata=metadata,
        )

        self.logs.append(log_entry)

        # 输出日志
        if self.enable_json:
            self.logger.info(log_entry.to_json_line())
        else:
            self.logger.info(
                f"[END] {phase} ({log_entry.duration_seconds}s) - {status}"
            )

        if error_message:
            self.logger.error(f"[ERROR] {phase}: {error_message}")

        return log_entry

    def log(self, level: str, message: str, **context) -> None:
        """
        记录带上下文的消息

        Args:
            level: 日志级别（INFO / WARNING / ERROR / DEBUG）
            message: 消息内容
            **context: 上下文字典
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **context,
        }

        if self.enable_json:
            self.logger.info(json.dumps(log_data, ensure_ascii=False))
        else:
            self.logger.log(
                getattr(logging, level, logging.INFO),
                f"{message} | {json.dumps(context)}",
            )

    def get_session_report(self) -> Dict[str, Any]:
        """生成会话日志报告"""
        total_duration = sum(log.duration_seconds for log in self.logs)
        phase_breakdown = {}

        for log in self.logs:
            if log.phase not in phase_breakdown:
                phase_breakdown[log.phase] = {
                    "count": 0,
                    "total_duration": 0.0,
                    "tokens": 0,
                    "status_counts": {},
                }
            phase_breakdown[log.phase]["count"] += 1
            phase_breakdown[log.phase]["total_duration"] += log.duration_seconds
            phase_breakdown[log.phase]["tokens"] += log.tokens_used
            status = log.status
            if status not in phase_breakdown[log.phase]["status_counts"]:
                phase_breakdown[log.phase]["status_counts"][status] = 0
            phase_breakdown[log.phase]["status_counts"][status] += 1

        return {
            "total_duration_seconds": round(total_duration, 2),
            "total_phases": len(self.logs),
            "phase_breakdown": phase_breakdown,
            "logs": [asdict(log) for log in self.logs],
        }

    def export_logs_json(self, filepath: str) -> None:
        """导出日志为 JSON 文件"""
        report = self.get_session_report()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        self.logger.info(f"日志已导出：{filepath}")


# 全局单例
_global_logger: Optional[StructuredLogger] = None


def get_logger(name: str = "crew-runner") -> StructuredLogger:
    """获取全局日志记录器实例"""
    global _global_logger
    if _global_logger is None:
        _global_logger = StructuredLogger(name=name)
    return _global_logger


def reset_logger() -> None:
    """重置全局日志记录器（用于测试）"""
    global _global_logger
    _global_logger = None
