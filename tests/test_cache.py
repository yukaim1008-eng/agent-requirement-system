"""
测试缓存模块
"""
import time
import pytest
from utils.cache import SessionCache, hash_requirement


class TestHashRequirement:
    """测试需求哈希"""

    def test_hash_is_consistent(self):
        """测试哈希一致性"""
        text = "做一个小程序"
        hash1 = hash_requirement(text)
        hash2 = hash_requirement(text)
        assert hash1 == hash2

    def test_different_text_different_hash(self):
        """测试不同文本产生不同哈希"""
        hash1 = hash_requirement("文本一")
        hash2 = hash_requirement("文本二")
        assert hash1 != hash2

    def test_hash_is_sha256(self):
        """测试哈希是 SHA256 格式"""
        h = hash_requirement("test")
        assert len(h) == 64  # SHA256 哈希长度
        assert all(c in "0123456789abcdef" for c in h)


class TestSessionCache:
    """测试会话缓存"""

    def test_set_and_get(self):
        """测试基本的设置和获取"""
        cache = SessionCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent_returns_none(self):
        """测试获取不存在的键"""
        cache = SessionCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        """测试 TTL 过期"""
        cache = SessionCache(default_ttl=1)  # 1 秒 TTL
        cache.set("key1", "value1", ttl=1)

        assert cache.get("key1") == "value1"

        # 等待过期
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_lru_eviction(self):
        """测试 LRU 驱逐"""
        cache = SessionCache(max_entries=2)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # 现在缓存满了，添加新的应该驱逐最旧的（key1）
        cache.set("key3", "value3")

        assert cache.get("key1") is None  # 被驱逐
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_lru_updates_on_access(self):
        """测试访问更新 LRU 顺序"""
        cache = SessionCache(max_entries=2)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # 访问 key1，更新其顺序
        _ = cache.get("key1")

        # 添加新的，应该驱逐 key2（最近最少使用）
        cache.set("key3", "value3")

        assert cache.get("key1") == "value1"  # 还在
        assert cache.get("key2") is None      # 被驱逐
        assert cache.get("key3") == "value3"

    def test_delete(self):
        """测试删除缓存"""
        cache = SessionCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        """测试清空缓存"""
        cache = SessionCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_get_stats(self):
        """测试统计信息"""
        cache = SessionCache(max_entries=5, default_ttl=10)

        cache.set("key1", "value1")
        cache.set("key2", "value2", ttl=1)

        time.sleep(1.1)  # key2 过期
        _ = cache.get("key2")  # 会被清理

        stats = cache.get_stats()
        assert stats["total_entries"] == 1  # 只有 key1
        assert stats["live_entries"] == 1
        assert stats["max_entries"] == 5

    def test_store_different_types(self):
        """测试存储不同类型的数据"""
        cache = SessionCache()

        cache.set("str", "value")
        cache.set("int", 42)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"key": "value"})

        assert cache.get("str") == "value"
        assert cache.get("int") == 42
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"key": "value"}
