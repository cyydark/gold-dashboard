"""数据源配置 — 可插拔架构.

切换数据源只需修改对应字典的条目，main.py 无需改动。

价格数据: SOURCES  — symbol -> (模块路径, fetch 函数名)
新闻数据: NEWS_SOURCES — name -> (模块路径, fetch_news 函数名)
"""
from backend.data.sources.binance_kline import fetch_xauusd_history as _xau
from backend.data.sources.eastmoney_au9999 import fetch_au9999_realtime as _au
from backend.data.sources.eastmoney_usdcnh import fetch_usdcny as _fx

# symbol -> (模块路径, 函数名)
SOURCES: dict[str, tuple[str, str]] = {
    "XAUUSD": ("backend.data.sources.binance_kline", "fetch_xauusd_history"),
    "AU9999": ("backend.data.sources.akshare_sge",    "fetch_au9999_history"),
    "USDCNY": ("backend.data.sources.yfinance_fx",     "fetch_usdcny"),
}

# name -> (模块路径, fetch_news 函数名)
NEWS_SOURCES: dict[str, tuple[str, str]] = {
    "futu":       ("backend.data.sources.futu",          "fetch_news"),
    "bernama":    ("backend.data.sources.bernama",       "fetch_news"),
    "bitcoinworld": ("backend.data.sources.bitcoinworld", "fetch_news"),
    "aastocks":   ("backend.data.sources.aastocks",      "fetch_news"),
}
