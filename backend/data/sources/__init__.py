"""数据源配置 — 可插拔架构.

每个 symbol 对应 (模块路径, 函数名)。
切换数据源只需修改 SOURCES 字典对应条目，main.py 无需改动。
"""
from backend.data.sources.binance_kline import fetch_xauusd_history as _xau
from backend.data.sources.fx678_au9999 import fetch_au9999_history as _au
from backend.data.sources.yfinance_fx import fetch_usdcny as _fx

# symbol -> (模块路径, 函数名)
SOURCES: dict[str, tuple[str, str]] = {
    "XAUUSD": ("backend.data.sources.binance_kline",  "fetch_xauusd_history"),
    "AU9999": ("backend.data.sources.akshare_sge",  "fetch_au9999_history"),
    "USDCNY": ("backend.data.sources.yfinance_fx",    "fetch_usdcny"),
}
