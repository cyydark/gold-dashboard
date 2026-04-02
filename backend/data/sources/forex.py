"""USD/CNY exchange rate data via Yahoo Finance."""
import yfinance as yf
from datetime import datetime


def fetch_usdcny(retry: int = 3) -> dict | None:
    """Fetch USD/CNY exchange rate via Yahoo Finance CNY=X ticker."""
    for _ in range(retry):
        try:
            ticker = yf.Ticker("CNY=X")
            data = ticker.history(period="2d", auto_adjust=True)
            if data.empty or len(data) < 1:
                continue

            latest = data.iloc[-1]
            prev = data.iloc[-2] if len(data) > 1 else latest

            price = float(latest["Close"])
            change = round(price - float(prev["Close"]), 4)
            pct = round((change / float(prev["Close"])) * 100, 4) if prev["Close"] else 0

            return {
                "symbol": "USDCNY",
                "name": "美元兑人民币 USD/CNY",
                "price": round(price, 4),
                "change": change,
                "pct": pct,
                "open": round(float(latest["Open"]), 4),
                "high": round(float(latest["High"]), 4),
                "low": round(float(latest["Low"]), 4),
                "unit": "CNY/USD",
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }
        except Exception:
            continue
    return None
