"""CME Gold Futures via omkarcloud CME Gold Price API.

数据源:  omkarcloud CME Gold Price API (https://gold-price-api.omkar.cloud/)
品种:    CME Gold Futures (XAU/USD)
单位:    USD / oz
SLA:     99.99%
免费额度: 5000 次/月
认证:    x-api-key (环境变量 OMKAR_API_KEY)
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_API_URL = "https://gold-price-api.omkar.cloud/price"

# ---------------------------------------------------------------------------
# 本地历史缓存 — 每次 fetch_xauusd_realtime() 成功时自动追加一条记录
# ---------------------------------------------------------------------------
_history: list[dict[str, Any]] = []


def _append_history(record: dict[str, Any]) -> None:
    """追加一条记录到本地历史缓存 (去重: 同一 timestamp 只存一条)。"""
    global _history
    if not any(r.get("timestamp") == record.get("timestamp") for r in _history):
        _history.append(record)


def _build_realtime_record(price: float, updated_at: str) -> dict[str, Any]:
    """从 API 原始响应构建标准化实时记录，并追加到历史缓存。"""
    # 解析 ISO 时间戳
    try:
        dt = datetime.fromisoformat(updated_at)
    except Exception:
        dt = datetime.now(timezone.utc)

    record = {
        "timestamp": int(dt.timestamp()),
        "iso_time":  updated_at,
        "price":     round(price, 2),
    }
    _append_history(record)
    return record


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def fetch_xauusd_realtime() -> dict[str, float] | None:
    """Fetch CME Gold Futures real-time price from omkarcloud API.

    Returns:
        {
            "price":  float,   # CME Gold price USD/oz
            "change": float,   # 涨跌额 (相对上一条缓存记录)
            "pct":    float,   # 涨跌幅 % (相对上一条缓存记录)
            "open":   float,   # 当日开盘估算 = 缓存中同日最早价格，若无则用 price
            "high":   float,   # 估算最高 = 缓存中同日最高价，若无则用 price
            "low":    float,   # 估算最低 = 缓存中同日最低价，若无则用 price
        }
        或 None (API Key 未配置 / 请求失败)。
    """
    api_key = os.environ.get("OMKAR_API_KEY")
    if not api_key:
        logger.info("OMKAR_API_KEY not set, skipping omkar CME")
        return None

    req = urllib.request.Request(
        _API_URL,
        headers={
            "x-api-key": api_key,
            "Accept":    "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        logger.warning(f"omkar CME request failed: {e}")
        return None

    price_usd: float | None = data.get("price_usd")
    updated_at: str | None = data.get("updated_at")

    if price_usd is None:
        logger.warning("omkar CME response missing 'price_usd'")
        return None

    record = _build_realtime_record(price_usd, updated_at or "")

    # ---------------------------------------------------------------------------
    # 涨跌额 / 涨跌幅 — 与缓存中前一条记录对比
    # ---------------------------------------------------------------------------
    change = 0.0
    pct    = 0.0

    if len(_history) >= 2:
        prev = _history[-2]
        change = round(price_usd - prev["price"], 2)
        prev_price = prev["price"]
        pct = round((change / prev_price) * 100, 2) if prev_price else 0.0

    # ---------------------------------------------------------------------------
    # open / high / low — 当日 (UTC) 统计
    # ---------------------------------------------------------------------------
    today = datetime.now(timezone.utc).date().isoformat()
    today_records = [r for r in _history if r.get("iso_time", "").startswith(today)]

    if today_records:
        prices = [r["price"] for r in today_records]
        open_  = round(prices[0],  2)
        high   = round(max(prices), 2)
        low    = round(min(prices), 2)
    else:
        open_  = round(price_usd, 2)
        high   = round(price_usd, 2)
        low    = round(price_usd, 2)

    return {
        "price":  round(price_usd, 2),
        "change": change,
        "pct":    pct,
        "open":   open_,
        "high":   high,
        "low":    low,
    }


def fetch_xauusd_history() -> list[dict[str, Any]] | None:
    """Return locally-cached CME Gold price history.

    每次 fetch_xauusd_realtime() 成功时会自动追加一条记录到本地缓存。
    本方法返回该缓存的完整列表 (按时间升序)。

    Returns:
        List of records [{timestamp, iso_time, price}, ...] 或 None (从未成功获取实时数据)。
    """
    if not _history:
        logger.info("omkar CME history cache is empty (no successful realtime fetches yet)")
        return None
    return list(_history)
