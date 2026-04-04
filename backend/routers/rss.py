"""RSS feed routes — 国际金价、国内金价、汇率、K线。

数据直接来自源 API：
  XAU/USD: Binance XAUT/USDT (24/7)
  AU9999:  Sina CFFEX 期货 au0 5分钟K线
  USD/CNY: er-api
"""
import json
import time
import threading
import re
from datetime import datetime, timezone, timedelta
from xml.sax.saxutils import escape
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import Response
import requests

BEIJING_TZ = timezone(timedelta(hours=8))
CACHE_TTL = 30

# 全局缓存
_cached: dict = {
    "xau": {"data": None, "ts": 0.0},
    "cny": {"data": None, "ts": 0.0},
    "fx":  {"data": None, "ts": 0.0},
}
_cache_lock = threading.Lock()

router = APIRouter(prefix="/rss", tags=["rss"])


# ---------------------------------------------------------------------------
# 数据获取
# ---------------------------------------------------------------------------

def _fetch_json(url: str) -> dict | None:
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[{datetime.now(BEIJING_TZ)}] Fetch error {url}: {e}")
        return None


def _fetch_xau_usd() -> dict:
    """Binance XAUT/USDT → 国际金价 XAU/USD"""
    data = _fetch_json("https://www.binance.com/api/v3/ticker/24hr?symbol=XAUTUSDT")
    if not data or not data.get("lastPrice"):
        raise RuntimeError("无法获取 Binance XAUT 价格")

    last = float(data["lastPrice"])
    open_px = float(data.get("openPrice", last))
    high = float(data["highPrice"])
    low = float(data["lowPrice"])
    change_pct = float(data.get("priceChangePercent", 0))

    return {
        "symbol": "XAUUSD",
        "name": "国际黄金 XAU/USD",
        "price": round(last, 2),
        "change": round(last - open_px, 2),
        "pct": round(change_pct, 2),
        "open": round(open_px, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "unit": "USD/oz",
        "updated_at": datetime.now(BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }


def _fetch_au9999() -> dict:
    """上海黄金交易所 AU9999 → 国内金价"""
    import akshare as ak

    df_spot = ak.spot_quotations_sge(symbol="Au99.99")
    latest_price = float(df_spot.iloc[-1]["现价"])

    df_hist = ak.spot_hist_sge(symbol="Au99.99")
    latest_day = df_hist.iloc[-1]
    prev_close = float(latest_day["close"])
    today_open = float(latest_day["open"])
    day_high = float(latest_day["high"])
    day_low = float(latest_day["low"])

    change = round(latest_price - prev_close, 2)
    pct = round((change / prev_close) * 100, 2) if prev_close else 0

    return {
        "symbol": "AU9999",
        "name": "国内黄金 AU9999",
        "price": round(latest_price, 2),
        "change": change,
        "pct": pct,
        "open": round(today_open or latest_price, 2),
        "high": round(day_high or latest_price, 2),
        "low": round(day_low or latest_price, 2),
        "unit": "CNY/g",
        "updated_at": datetime.now(BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }


def _fetch_usd_cny() -> dict:
    """er-api → USD/CNY 汇率"""
    data = _fetch_json("https://open.er-api.com/v6/latest/USD")
    if not data:
        raise RuntimeError("无法获取 USD/CNY 汇率")
    rate = float(data["rates"]["CNY"])
    return {
        "symbol": "USDCNY",
        "name": "美元兑人民币 USD/CNY",
        "price": round(rate, 4),
        "unit": "CNY/USD",
        "updated_at": datetime.now(BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }


# ---------------------------------------------------------------------------
# 缓存读取
# ---------------------------------------------------------------------------

def _get_cached(endpoint: str, fetch_fn):
    now = time.time()
    cache = _cached[endpoint]
    if cache["data"] is not None and (now - cache["ts"]) < CACHE_TTL:
        return cache["data"]
    try:
        data = fetch_fn()
        with _cache_lock:
            _cached[endpoint]["data"] = data
            _cached[endpoint]["ts"] = now
        return data
    except Exception as e:
        print(f"[{datetime.now(BEIJING_TZ)}] {endpoint} fetch error: {e}")
        with _cache_lock:
            if cache["data"] is not None:
                return cache["data"]
        return None


# ---------------------------------------------------------------------------
# RSS 构建
# ---------------------------------------------------------------------------

def _fmt_price(data: dict) -> str:
    price = data.get("price")
    change = data.get("change")
    pct = data.get("pct", 0)
    open_px = data.get("open")
    sign = "+" if (change or 0) >= 0 else ""
    color = "#22c55e" if pct >= 0 else "#ef4444"
    parts = [
        f"<b>{escape(data.get('name', ''))}：</b> "
        f"{price:,.2f} {data.get('unit', '')} "
        f"<span style='color:{color}'>({sign}{pct:+.2f}%)</span><br/>",
        f"<b>24h 高/低：</b> {data.get('high', '—'):,.2f} / {data.get('low', '—'):,.2f}<br/>",
    ]
    if open_px is not None:
        parts.append(f"<b>开盘：</b> {open_px:,.2f} | <b>涨跌：</b> {sign}{change:,.2f}<br/>")
    return "".join(parts)


def _build_rss(endpoint: str) -> str:
    now = datetime.now(BEIJING_TZ)
    now_str = now.strftime("%a, %d %b %Y %H:%M:%S +0800")
    time_str = now.strftime("%H:%M:%S")

    if endpoint == "xau":
        xau = _get_cached("xau", _fetch_xau_usd)
        if not xau:
            return _error_rss("无法获取国际金价数据")
        desc = _fmt_price(xau)
        title = f"国际金价 {xau['price']:,.2f} USD/oz ({'+' if xau['pct'] >= 0 else ''}{xau['pct']:.2f}%)"
        link = "https://www.binance.com/zh-CN/trade/XAUT_USDT"
    elif endpoint == "cny":
        cny_gold = _get_cached("cny", _fetch_au9999)
        if not cny_gold:
            return _error_rss("无法获取国内金价数据")
        desc = _fmt_price(cny_gold)
        title = f"国内金价 AU9999 {cny_gold['price']:,.2f} CNY/g"
        link = "https://www.sge.com.cn/"
    elif endpoint == "fx":
        fx = _get_cached("fx", _fetch_usd_cny)
        if not fx:
            return _error_rss("无法获取汇率数据")
        desc = (
            f"<b>{escape(fx.get('name', ''))}：</b> "
            f"{fx['price']:,.4f} {fx.get('unit', '')}<br/>"
        )
        title = f"USD/CNY 汇率 {fx['price']:,.4f}"
        link = "https://open.er-api.com/"
    else:  # combined /
        xau = _get_cached("xau", _fetch_xau_usd)
        cny_gold = _get_cached("cny", _fetch_au9999)
        fx = _get_cached("fx", _fetch_usd_cny)
        parts = []
        if xau:
            parts.append(_fmt_price(xau))
        if cny_gold:
            parts.append(_fmt_price(cny_gold))
        if fx:
            parts.append(f"<b>{escape(fx.get('name', ''))}：</b> {fx['price']:,.4f} {fx.get('unit', '')}<br/>")
        desc = "<br/>".join(parts)
        title = f"实时金价 & 汇率汇总 | 更新于 {time_str}"
        link = "https://www.binance.com/zh-CN/trade/XAUT_USDT"

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{title}</title>
    <link>{link}</link>
    <description>gold-dashboard 实时数据 RSS</description>
    <language>zh-CN</language>
    <lastBuildDate>{now_str}</lastBuildDate>
    <ttl>1</ttl>
    <atom:link href="/rss/{endpoint}" rel="self" type="application/rss+xml"/>
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <guid isPermaLink="false">gold-dashboard-{endpoint}-{now.strftime("%Y%m%d%H%M%S")}</guid>
      <pubDate>{now_str}</pubDate>
      <description><![CDATA[{desc}]]></description>
    </item>
  </channel>
</rss>'''


def _error_rss(msg: str) -> str:
    now_str = datetime.now(BEIJING_TZ).strftime("%a, %d %b %Y %H:%M:%S +0800")
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>数据获取失败</title>
    <lastBuildDate>{now_str}</lastBuildDate>
    <item>
      <title>错误</title>
      <pubDate>{now_str}</pubDate>
      <description><![CDATA[{msg}]]></description>
    </item>
  </channel>
</rss>'''


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

@router.get("/")
async def rss_all():
    """合并：国际金价 + 国内金价 + 汇率"""
    from fastapi.responses import Response
    return Response(content=_build_rss("all"), media_type="application/rss+xml; charset=utf-8")


@router.get("/xau")
async def rss_xau():
    """国际金价 XAU/USD（Binance XAUT/USDT）"""
    from fastapi.responses import Response
    return Response(content=_build_rss("xau"), media_type="application/rss+xml; charset=utf-8")


@router.get("/cny")
async def rss_cny():
    """国内金价 AU9999 元/克（上海黄金交易所）"""
    from fastapi.responses import Response
    return Response(content=_build_rss("cny"), media_type="application/rss+xml; charset=utf-8")


@router.get("/fx")
async def rss_fx():
    """USD/CNY 汇率（er-api）"""
    return Response(content=_build_rss("fx"), media_type="application/rss+xml; charset=utf-8")


# ---------------------------------------------------------------------------
# K线缓存
# ---------------------------------------------------------------------------
_HIST_XAU_CACHE: list = []
_HIST_XAU_TS: float = 0.0
_HIST_AU_CACHE: list = []
_HIST_AU_TS: float = 0.0
_HIST_TTL = 60  # 1 分钟


def _fetch_xau_history() -> list[dict] | None:
    """Binance XAUT/USDT 5分钟K线，≈3.5天（1000条）。"""
    resp = requests.get(
        "https://www.binance.com/api/v3/klines?symbol=XAUTUSDT&interval=5m&limit=1000",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=10,
        verify=False,
    )
    resp.raise_for_status()
    klines = resp.json()
    records = []
    for k in klines:
        records.append({
            "time": int(k[0]) // 1000,
            "open":  round(float(k[1]), 2),
            "high":  round(float(k[2]), 2),
            "low":   round(float(k[3]), 2),
            "close": round(float(k[4]), 2),
            "volume": 0,
        })
    records.sort(key=lambda x: x["time"])
    return records if records else None


def _fetch_au_history() -> list[dict] | None:
    """Sina CFFEX 期货 au0 5分钟K线。"""
    url = (
        "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
        "=/InnerFuturesNewService.getFewMinLine?symbol=au0&type=5"
    )
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, verify=False)
    resp.raise_for_status()
    text = resp.text
    idx = text.find("=(")
    if idx < 0:
        idx = text.find("[")
    raw = text[idx + 2:].rstrip().rstrip(";").rstrip(")")
    bars = json.loads(raw)
    records = []
    for b in bars:
        dt_str = b.get("d", "")
        if not dt_str:
            continue
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BEIJING_TZ)
        except Exception:
            continue
        records.append({
            "time": int(dt.timestamp()),
            "open":  round(float(b.get("o", 0)), 2),
            "high":  round(float(b.get("h", 0)), 2),
            "low":   round(float(b.get("l", 0)), 2),
            "close": round(float(b.get("c", 0)), 2),
            "volume": 0,
        })
    records.sort(key=lambda x: x["time"])
    return records if records else None


# ---------------------------------------------------------------------------
# K线路由
# ---------------------------------------------------------------------------

@router.get("/history/xau")
async def history_xau():
    """XAU/USD 5分钟K线 JSON（内部路由，供 dashboard 调用）。"""
    global _HIST_XAU_CACHE, _HIST_XAU_TS
    now = time.time()
    if _HIST_XAU_CACHE and (now - _HIST_XAU_TS) < _HIST_TTL:
        bars = _HIST_XAU_CACHE
    else:
        try:
            bars = _fetch_xau_history()
        except Exception as e:
            print(f"[{datetime.now(BEIJING_TZ)}] XAU history error: {e}")
            bars = []
        if bars:
            _HIST_XAU_CACHE = bars
            _HIST_XAU_TS = now
    if not bars:
        return {"bars": [], "xMin": 0, "xMax": 0}
    return {"bars": bars, "xMin": bars[0]["time"], "xMax": bars[-1]["time"]}


@router.get("/history/au")
async def history_au():
    """AU9999 5分钟K线 JSON（内部路由，供 dashboard 调用）。"""
    global _HIST_AU_CACHE, _HIST_AU_TS
    now = time.time()
    if _HIST_AU_CACHE and (now - _HIST_AU_TS) < _HIST_TTL:
        bars = _HIST_AU_CACHE
    else:
        try:
            bars = _fetch_au_history()
        except Exception as e:
            print(f"[{datetime.now(BEIJING_TZ)}] AU history error: {e}")
            bars = []
        if bars:
            _HIST_AU_CACHE = bars
            _HIST_AU_TS = now
    if not bars:
        return {"bars": [], "xMin": 0, "xMax": 0}
    return {"bars": bars, "xMin": bars[0]["time"], "xMax": bars[-1]["time"]}
