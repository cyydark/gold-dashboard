"""
内存 TTL 缓存模块。
每个缓存项：{"data": ..., "ts": 时间戳}
每次 get 时检查 TTL，过期返回 None。
"""
import time
from threading import Lock
from typing import Any


class TTLCache:
    """线程安全的 TTL 内存缓存。"""

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            if time.monotonic() - item["ts"] > self._ttl:
                del self._store[key]
                return None
            return item["data"]

    def set(self, key: str, data: Any) -> None:
        with self._lock:
            self._store[key] = {"data": data, "ts": time.monotonic()}

    def clear(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear_all(self) -> None:
        with self._lock:
            self._store.clear()
