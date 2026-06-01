"""
缓存层 —— 减少重复 API 调用

特性：
  - LRU 缓存（内存）
  - TTL 支持
  - 需求 hash 缓存
  - 查询结果缓存
"""
import hashlib
import json
import time
import logging
from typing import Optional, Any, Dict, Callable
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def hash_requirement(text: str) -> str:
    """生成需求的 SHA256 哈希值"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class CacheEntry:
    """缓存条目"""

    def __init__(self, key: str, value: Any, ttl_seconds: int = 86400):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds

    def is_expired(self) -> bool:
        """检查是否过期"""
        return (time.time() - self.created_at) > self.ttl_seconds

    def age_seconds(self) -> int:
        """返回缓存年龄（秒）"""
        return int(time.time() - self.created_at)


class SessionCache:
    """会话级缓存（内存）"""

    def __init__(self, max_entries: int = 100, default_ttl: int = 86400):
        """
        初始化缓存

        Args:
            max_entries: 最大缓存条目数（LRU）
            default_ttl: 默认 TTL（秒，默认 24h）
        """
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: list = []  # 用于 LRU

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值
            ttl: TTL（秒），None 则用默认值
        """
        ttl = ttl or self.default_ttl

        # LRU：如果已满，删除最久未访问的
        if len(self.cache) >= self.max_entries and key not in self.cache:
            if self.access_order:
                oldest_key = self.access_order.pop(0)
                del self.cache[oldest_key]
                logger.debug(f"[CACHE] LRU 驱逐：{oldest_key}")

        self.cache[key] = CacheEntry(key, value, ttl)
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)

        logger.debug(f"[CACHE] 写入缓存：{key[:16]}...（TTL {ttl}s）")

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存

        Args:
            key: 缓存键

        Returns:
            缓存值，或 None（不存在或已过期）
        """
        if key not in self.cache:
            return None

        entry = self.cache[key]

        # 检查过期
        if entry.is_expired():
            logger.debug(f"[CACHE] 缓存已过期：{key[:16]}...（年龄 {entry.age_seconds()}s）")
            del self.cache[key]
            return None

        # 更新访问顺序（LRU）
        self.access_order.remove(key)
        self.access_order.append(key)

        logger.debug(f"[CACHE] 命中缓存：{key[:16]}...")
        return entry.value

    def delete(self, key: str) -> None:
        """删除缓存条目"""
        if key in self.cache:
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)
            logger.debug(f"[CACHE] 删除缓存：{key[:16]}...")

    def clear(self) -> None:
        """清空所有缓存"""
        self.cache.clear()
        self.access_order.clear()
        logger.info("[CACHE] 已清空所有缓存")

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        expired_count = sum(1 for e in self.cache.values() if e.is_expired())
        return {
            "total_entries": len(self.cache),
            "expired_entries": expired_count,
            "live_entries": len(self.cache) - expired_count,
            "max_entries": self.max_entries,
        }


class FileCache:
    """文件系统级缓存（持久化）"""

    def __init__(self, cache_dir: str = "./cache", default_ttl: int = 86400):
        """
        初始化文件缓存

        Args:
            cache_dir: 缓存目录
            default_ttl: 默认 TTL（秒）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.default_ttl = default_ttl
        self.index_file = self.cache_dir / ".index.json"
        self.index = self._load_index()

    def _load_index(self) -> dict:
        """加载缓存索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"[CACHE] 无法加载索引：{e}")
        return {}

    def _save_index(self) -> None:
        """保存缓存索引"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[CACHE] 保存索引失败：{e}")

    def _get_cache_path(self, key: str) -> Path:
        """根据键生成缓存文件路径"""
        return self.cache_dir / f"{key}.json"

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        ttl = ttl or self.default_ttl
        cache_path = self._get_cache_path(key)

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False)

            # 更新索引
            self.index[key] = {
                "created_at": datetime.now().isoformat(),
                "ttl": ttl,
            }
            self._save_index()
            logger.debug(f"[CACHE] 文件缓存写入：{key[:16]}...（TTL {ttl}s）")
        except Exception as e:
            logger.error(f"[CACHE] 文件缓存写入失败：{e}")

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self.index:
            return None

        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            return None

        # 检查 TTL
        meta = self.index[key]
        created_at = datetime.fromisoformat(meta["created_at"])
        ttl = meta.get("ttl", self.default_ttl)
        if datetime.now() - created_at > timedelta(seconds=ttl):
            logger.debug(f"[CACHE] 文件缓存已过期：{key[:16]}...")
            self.delete(key)
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[CACHE] 文件缓存读取失败：{e}")
            return None

    def delete(self, key: str) -> None:
        """删除缓存"""
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
        if key in self.index:
            del self.index[key]
            self._save_index()
        logger.debug(f"[CACHE] 删除文件缓存：{key[:16]}...")

    def cleanup_expired(self) -> int:
        """清理过期缓存，返回清理数量"""
        expired_keys = []
        for key, meta in self.index.items():
            created_at = datetime.fromisoformat(meta["created_at"])
            ttl = meta.get("ttl", self.default_ttl)
            if datetime.now() - created_at > timedelta(seconds=ttl):
                expired_keys.append(key)

        for key in expired_keys:
            self.delete(key)

        logger.info(f"[CACHE] 清理了 {len(expired_keys)} 个过期缓存")
        return len(expired_keys)


# 全局实例
_session_cache: Optional[SessionCache] = None


def get_session_cache() -> SessionCache:
    """获取全局会话缓存实例"""
    global _session_cache
    if _session_cache is None:
        _session_cache = SessionCache()
    return _session_cache


def cache_result(key: str, func: Callable, ttl: Optional[int] = None) -> Any:
    """
    缓存函数结果的便利方法

    Args:
        key: 缓存键
        func: 计算结果的函数
        ttl: TTL（秒）

    Returns:
        缓存的或新计算的结果
    """
    cache = get_session_cache()
    cached = cache.get(key)
    if cached is not None:
        return cached

    result = func()
    cache.set(key, result, ttl=ttl)
    return result
