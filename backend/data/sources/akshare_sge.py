"""国内金价 AU9999 via akshare SGE 实时行情。

数据源: 上海黄金交易所 akshare.spot_quotations_sge
品种: Au99.99
粒度: 1分钟
注意: 该接口返回的不是真实历史分钟数据，而是以当前最新价填充每个分钟槽位，
      适合看盘口实时价，不适合画历史 K 线。
"""
import logging
import pandas as pd
import akshare as ak
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))


def _parse_update_date(df: pd.DataFrame) -> datetime | None:
    """从第一行'更新时间'字段解析出实际日期。"""
    if df is None or df.empty:
        return None
    col = "更新时间"
    if col not in df.columns:
        return None
    raw = str(df.iloc[0][col]).strip()
    # "2026年04月03日 15:45:00"
    try:
        return datetime.strptime(raw[: len("2026年04月03日 15:45:00") - 9], "%Y年%m月%d日")
    except Exception:
        return None


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

        update_date = _parse_update_date(df)
        if update_date is None:
            logger.warning("akshare SGE: failed to parse update date")
            return None
        update_date = update_date.replace(tzinfo=BEIJING_TZ)

        records = []
        for _, row in df.iterrows():
            time_str = str(row["时间"])
            dt = datetime.strptime(f"{update_date.date()} {time_str}", "%Y-%m-%d %H:%M:%S")
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
