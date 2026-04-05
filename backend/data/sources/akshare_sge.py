"""国内金价 AU9999 via akshare SGE 实时行情。

数据源: 上海黄金交易所 akshare.spot_quotations_sge
品种: Au99.99
粒度: 1分钟
注意: 该接口返回的不是真实历史分钟数据，而是以当前最新价填充每个分钟槽位，
      适合看盘口实时价，不适合画历史 K 线。
      只在数据日期变化时导入新数据，同一天不重复导入。
"""
import logging
import os
import pandas as pd
import akshare as ak
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "alerts.db")


def _parse_update_date(df: pd.DataFrame) -> datetime | None:
    """从第一行'更新时间'字段解析出实际日期。"""
    if df is None or df.empty:
        return None
    col = "更新时间"
    if col not in df.columns:
        return None
    raw = str(df.iloc[0][col]).strip()
    # "2026年04月03日 15:45:00" — 取前11字符得到日期部分
    try:
        return datetime.strptime(raw[:11], "%Y年%m月%d日")
    except Exception:
        return None


def _has_data_for_date(trading_date: datetime.date) -> bool:
    """检查数据库是否已有该日期的 AU9999 数据。"""
    import sqlite3
    start = datetime(trading_date.year, trading_date.month, trading_date.day,
                      tzinfo=BEIJING_TZ)
    end = start + timedelta(days=1)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM price_bars WHERE symbol='AU9999' AND ts >= ? AND ts < ?",
                (int(start.timestamp()), int(end.timestamp()))
            )
            return cur.fetchone()[0] > 0
    except Exception:
        return False


def fetch_au9999_history() -> list[dict] | None:
    """Fetch AU9999 1m bars from SGE.

    Returns bars only if the trading date is new (not yet in DB).
    Returns None if today's data already exists in DB.
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

        if _has_data_for_date(update_date.date()):
            logger.info(f"akshare SGE: data for {update_date.date()} already exists, skipping")
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
