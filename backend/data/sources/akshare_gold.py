"""沪金期货主力连续 AU0 via AkShare.

数据源: AkShare开源库 -> 新浪财经 -> 沪金期货主力连续 AU0
品种: 沪金期货 (CNY/g)
粒度: 5分钟K线
"""
import logging
from typing import Any

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)


def fetch_au_history() -> list[dict[str, Any]] | None:
    """Fetch 沪金期货主力连续 AU0 5-minute K线 history.

    Returns:
        List of bars [{time, open, high, low, close, volume, change, pct}, ...]
        or None on error.
    """
    try:
        df = ak.futures_zh_minute_sina(symbol="au0", period="5")
        if df is None or df.empty:
            logger.warning("akshare futures_zh_minute_sina au0: no data returned")
            return None

        records = []
        for _, row in df.iterrows():
            # date 列可能是 datetime 或字符串
            ts = row["datetime"]
            if not isinstance(ts, (int, float)):
                ts = pd.Timestamp(ts).timestamp()
            records.append({
                "time":   int(ts),
                "open":   round(float(row["open"]), 2),
                "high":   round(float(row["high"]), 2),
                "low":    round(float(row["low"]), 2),
                "close":  round(float(row["close"]), 2),
                "volume": float(row["volume"]) if "volume" in row else 0.0,
                "change": 0.0,
                "pct":    0.0,
            })
        return records if records else None
    except Exception as e:
        logger.warning(f"akshare futures_zh_minute_sina au0 error: {e}")
        return None


def fetch_au_realtime() -> dict[str, Any] | None:
    """Fetch 沪金期货 AU0 实时行情 via futures_zh_spot.

    Returns:
        Dict with {price, change, pct, open, high, low} or None on error.
    """
    try:
        # market="CF" for commodity futures, symbol="AU0" for 沪金主力连续
        df = ak.futures_zh_spot(symbol="AU0", market="CF", adjust="0")
        if df is None or df.empty:
            logger.warning("akshare futures_zh_spot AU0: no data returned")
            return None

        price = float(df.iloc[0]["current_price"])
        open_ = float(df.iloc[0]["open"])
        high = float(df.iloc[0]["high"])
        low = float(df.iloc[0]["low"])
        last_close = float(df.iloc[0]["last_close"])
        change = round(price - last_close, 2)
        pct = round((price - last_close) / last_close * 100, 2) if last_close else 0.0

        return {
            "price":  price,
            "change": change,
            "pct":    pct,
            "open":   open_,
            "high":   high,
            "low":    low,
        }
    except Exception as e:
        logger.warning(f"akshare futures_zh_spot AU0 error: {e}")
        return None
