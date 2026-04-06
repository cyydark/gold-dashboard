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
            ts = row["date"]
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
    """Fetch 沪金期货 AU0 实时行情.

    Returns:
        Dict with {price, change, pct, open, high, low} or None on error.
    """
    try:
        df = ak.futures_zh_a_spot()
        if df is None or df.empty:
            logger.warning("akshare futures_zh_a_spot: no data returned")
            return None

        cols = df.columns.tolist()
        col_lower = [str(c).lower() for c in cols]

        # 定位品种列（包含"品种"或"代码"的列），用于筛选
        symbol_col_idx: int | None = None
        for i, c in enumerate(col_lower):
            if "品种" in c or "代码" in c or "合约" in c:
                symbol_col_idx = i
                break

        def row_contains_au(row: pd.Series) -> bool:
            if symbol_col_idx is not None:
                val = str(row.iloc[symbol_col_idx]).lower()
                return "au0" in val or "沪金" in val
            return "au0" in " ".join(str(v).lower() for v in row.values)

        mask = df.apply(row_contains_au, axis=1)
        if not mask.any():
            logger.warning("akshare futures_zh_a_spot: no 沪金 contract found")
            return None

        row = df[mask].iloc[0]

        def get_float(val: Any) -> float:
            try:
                return float(val)
            except (TypeError, ValueError):
                return 0.0

        # 尝试通过列名定位所需字段
        price = change = pct = open_ = high = low = 0.0
        for i, c in enumerate(col_lower):
            if "最新价" in c or "现价" in c or "收盘" in c:
                price = get_float(row.iloc[i])
            elif "涨跌额" in c or "涨跌" in c:
                change = get_float(row.iloc[i])
            elif "涨跌幅" in c and "涨跌额" not in c:
                pct = get_float(row.iloc[i])
            elif "开盘" in c and "最高" not in c and "最低" not in c:
                open_ = get_float(row.iloc[i])
            elif "最高" in c:
                high = get_float(row.iloc[i])
            elif "最低" in c:
                low = get_float(row.iloc[i])

        return {
            "price":  price,
            "change": change,
            "pct":    pct,
            "open":   open_,
            "high":   high,
            "low":    low,
        }
    except Exception as e:
        logger.warning(f"akshare futures_zh_a_spot error: {e}")
        return None
