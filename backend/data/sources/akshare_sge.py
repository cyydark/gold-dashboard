"""国内金价 AU9999 via akshare SGE 实时行情。

数据源: 上海黄金交易所 akshare.spot_quotations_sge
品种: Au99.99
粒度: 1分钟
历史深度: 当日（约 700 交易日分钟数据）
"""
import logging
import pandas as pd
import akshare as ak
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))


def fetch_au9999_history() -> list[dict] | None:
    """Fetch AU9999 1m K-line from SGE minute-level data.

    Returns:
        List of bars [{time, open, high, low, close, volume}, ...] or None on error.
    """
    try:
        df = ak.spot_quotations_sge(symbol="Au99.99")
        if df is None or df.empty:
            logger.warning("akshare SGE: no data returned")
            return None

        today = datetime.now(BEIJING_TZ).date()

        records = []
        for _, row in df.iterrows():
            time_str = row["时间"]  # "HH:MM:SS"
            dt = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=BEIJING_TZ)
            price = float(row["现价"])
            records.append({
                "time":  int(dt.timestamp()),
                "open":  price,
                "high":  price,
                "low":   price,
                "close": price,
                "volume": 0,
            })

        return records if records else None
    except Exception as e:
        logger.warning(f"akshare SGE AU9999 error: {e}")
        return None
