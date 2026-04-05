"""国际金价 via yfinance (CME COMEX Gold Futures GC=F).

数据源: Yahoo Finance GC=F (Gold Futures, 100oz)
Ticker: GC=F
粒度: 1分钟 (1m)
历史深度: 8天 (上限)
"""
import logging
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_gold_futures() -> list[dict] | None:
    """Fetch COMEX Gold (GC=F) OHLCV via yfinance (1m, 7d).

    Returns:
        List of bars [{time, open, high, low, close, volume}, ...] or None on error.
    """
    try:
        ticker = yf.Ticker("GC=F")
        # yfinance 1m 最多支持 ~8天
        hist = ticker.history(period="7d", interval="1m")
        if hist.empty:
            logger.warning("yfinance GC=F: no data returned")
            return None

        records = []
        for ts, row in hist.iterrows():
            records.append({
                "time":  int(ts.timestamp()),
                "open":  round(float(row["Open"]), 2),
                "high":  round(float(row["High"]), 2),
                "low":   round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if "Volume" in row else 0,
            })
        return records if records else None
    except Exception as e:
        logger.warning(f"yfinance GC=F error: {e}")
        return None
