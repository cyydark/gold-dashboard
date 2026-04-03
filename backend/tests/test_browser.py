"""Tests for BrowserManager."""
import pytest
import threading
import time
from backend.data.sources.browser import BrowserManager


def test_singleton():
    """验证 BrowserManager 是单例。"""
    b1 = BrowserManager()
    b2 = BrowserManager()
    assert b1 is b2


def test_thread_safety():
    """验证多线程访问不崩溃（不验证真实浏览器启动，只验证锁机制）。"""
    results = []
    errors = []

    def get_browser():
        try:
            bm = BrowserManager()
            # 不真正启动浏览器，只验证 lock 不冲突
            results.append(id(bm))
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=get_browser) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(set(results)) == 1  # 同一实例


def test_launch_close_idempotent():
    """验证 launch/close 幂等。"""
    bm = BrowserManager()
    bm.launch()
    bm.launch()  # 重复 launch 不报错
    bm.close()
    bm.close()  # 重复 close 不报错
