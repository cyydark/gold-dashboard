"""美元/离岸人民币 (USDCNY) via yfinance.

数据源: Yahoo Finance USDCNY=X
Ticker: USDCNY=X
粒度: 5分钟 (5m)
历史深度: ~70天
"""
import logging
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_usdcny() -> list[dict] | None:
    """Fetch USDCNY (USD/CNY) OHLCV via yfinance (5m, 60d).

    Returns:
        List of bars [{time, open, high, low, close, volume}, ...] or None on error.
    """
    try:
        ticker = yf.Ticker("USDCNY=X")
        hist = ticker.history(period="60d", interval="5m")
        if hist.empty:
            logger.warning("yfinance USDCNY=X: no data returned")
            return None

        records = []
        for ts, row in hist.iterrows():
            records.append({
                "time":  int(ts.timestamp()),
                "open":  round(float(row["Open"]), 4),
                "high":  round(float(row["High"]), 4),
                "low":   round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]) if "Volume" in row else 0,
            })
        return records if records else None
    except Exception as e:
        logger.warning(f"yfinance USDCNY=X error: {e}")
        return None
