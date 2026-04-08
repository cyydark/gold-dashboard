"""Price API routes — realtime price, chart bars, FX rates."""
import logging
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

# ── Fetcher registry ────────────────────────────────────────────────
# Import all modules once at startup and cache function references.
# Avoids the expensive sys.modules purge on every request.
import importlib

_MODULES = {
    "backend.data.sources.sina_xau":               importlib.import_module("backend.data.sources.sina_xau"),
    "backend.data.sources.binance_kline":          importlib.import_module("backend.data.sources.binance_kline"),
    "backend.data.sources.sina_au9999":            importlib.import_module("backend.data.sources.sina_au9999"),
    "backend.data.sources.eastmoney_au9999_price": importlib.import_module("backend.data.sources.eastmoney_au9999_price"),
    "backend.data.sources.yfinance_fx":            importlib.import_module("backend.data.sources.yfinance_fx"),
    "backend.data.sources.sina_fx":                importlib.import_module("backend.data.sources.sina_fx"),
    "backend.data.sources.eastmoney_xauusd":       importlib.import_module("backend.data.sources.eastmoney_xauusd"),
    "backend.data.sources.sina_au0_1m":             importlib.import_module("backend.data.sources.sina_au0_1m"),
}

def _fn(mod_name: str, fn_name: str):
    return getattr(_MODULES[mod_name], fn_name)

# ── XAU realtime fetchers ──────────────────────────────────────────
_XAU_FETCHERS = {
    "sina":    ("backend.data.sources.sina_xau",               "fetch_xauusd_realtime"),
    "comex":   ("backend.data.sources.sina_xau",               "fetch_xauusd_realtime"),
    "binance": ("backend.data.sources.binance_kline",          "fetch_xauusd_realtime"),
}

# ── AU realtime fetchers ───────────────────────────────────────────
_AU_FETCHERS = {
    "au9999":    ("backend.data.sources.sina_au9999",            "fetch_au9999_realtime"),
    "eastmoney": ("backend.data.sources.eastmoney_au9999_price", "fetch_au9999_realtime"),
}

# ── FX fetchers ────────────────────────────────────────────────────
_FX_FETCHERS = {
    "yfinance": ("backend.data.sources.yfinance_fx", "fetch_usdcny"),
    "sina":     ("backend.data.sources.sina_fx",     "fetch_usdcny"),
}

# ── Chart bar fetchers ─────────────────────────────────────────────
_XAU_BAR_FETCHERS = {
    "comex":   ("backend.data.sources.eastmoney_xauusd", "fetch_xauusd_history"),
    "binance": ("backend.data.sources.binance_kline",     "fetch_xauusd_kline"),
    "sina":    ("backend.data.sources.eastmoney_xauusd", "fetch_xauusd_history"),
}
_AU_BAR_FETCHERS = {
    "au9999":   ("backend.data.sources.eastmoney_au9999", "fetch_au9999_realtime"),
    "sina_au0": ("backend.data.sources.sina_au0_1m",      "fetch_au9999_realtime"),
}

router = APIRouter(prefix="/api", tags=["price"])


def _fetch(source: str, fetchers: dict):
    """Call the configured fetcher for `source`."""
    if source not in fetchers:
        return None
    mod_name, fn_name = fetchers[source]
    try:
        return _fn(mod_name, fn_name)()
    except Exception as e:
        logger.warning(f"_fetch({source}) failed: {e}")
        return None


def _build_xau_resp(bar, now_ts: int):
    if bar is None:
        return {"error": "数据获取失败，请切换数据源", "price": None}
    return {
        "price": round(float(bar.get("price", bar.get("close", 0))), 2),
        "change": round(float(bar.get("change", 0)), 2),
        "pct": round(float(bar.get("pct", 0)), 4),
        "open": round(float(bar.get("open", bar.get("price", 0))), 2),
        "high": round(float(bar.get("high", bar.get("price", 0))), 2),
        "low": round(float(bar.get("low", bar.get("price", 0))), 2),
        "unit": "USD/oz",
        "ts": now_ts,
        "updated_at": datetime.fromtimestamp(now_ts, BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }


def _build_au_resp(bar, now_ts: int):
    if bar is None:
        return {"error": "数据获取失败，请切换数据源", "price": None}
    return {
        "price": round(float(bar.get("price", bar.get("close", 0))), 2),
        "change": round(float(bar.get("change", 0)), 2),
        "pct": round(float(bar.get("pct", 0)), 2),
        "open": round(float(bar.get("open", bar.get("price", 0))), 2),
        "high": round(float(bar.get("high", bar.get("price", 0))), 2),
        "low": round(float(bar.get("low", bar.get("price", 0))), 2),
        "unit": "CNY/g",
        "ts": now_ts,
        "updated_at": datetime.fromtimestamp(now_ts, BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }


def _build_fx_resp(bar):
    if bar is None:
        return {"error": "数据获取失败，请切换数据源", "price": None}
    return {
        "price": round(float(bar.get("price", bar.get("close", 0))), 4),
        "change": round(float(bar.get("change", 0)), 4),
        "pct": round(float(bar.get("pct", 0)), 4),
        "open": round(float(bar.get("open", bar.get("price", 0))), 4),
        "high": round(float(bar.get("high", bar.get("price", 0))), 4),
        "low": round(float(bar.get("low", bar.get("price", 0))), 4),
        "unit": "CNY/USD",
        "ts": bar.get("ts", int(time.time())),
    }


@router.get("/realtime/xau/{source}")
def get_xau_realtime(source: str):
    bar = _fetch(source, _XAU_FETCHERS)
    return _build_xau_resp(bar, int(time.time()))


@router.get("/realtime/au/{source}")
def get_au_realtime(source: str):
    bar = _fetch(source, _AU_FETCHERS)
    return _build_au_resp(bar, int(time.time()))


@router.get("/realtime/fx/{source}")
def get_fx_realtime(source: str):
    raw = _fetch(source, _FX_FETCHERS)
    # yfinance returns a list of bars; take the last one for the "current" rate
    if isinstance(raw, list) and raw:
        raw = raw[-1]
    return _build_fx_resp(raw)


@router.get("/chart/xau")
def get_chart_xau(source: str = Query(default="comex")):
    bars_raw = _fetch(source, _XAU_BAR_FETCHERS)
    if bars_raw is None:
        return {"bars": [], "source": source}
    bars = []
    for b in bars_raw:
        bars.append({
            "time": b.get("time", b.get("ts", 0)),
            "open": round(float(b.get("open", b.get("close", 0))), 2),
            "high": round(float(b.get("high", b.get("close", 0))), 2),
            "low": round(float(b.get("low", b.get("close", 0))), 2),
            "close": round(float(b.get("close", b.get("price", 0))), 2),
        })
    return {"bars": bars, "source": source}


@router.get("/chart/au")
def get_chart_au(source: str = Query(default="au9999")):
    bars_raw = _fetch(source, _AU_BAR_FETCHERS)
    if bars_raw is None:
        return {"bars": [], "source": source}
    bars = []
    for b in bars_raw:
        bars.append({
            "time": b.get("time", b.get("ts", 0)),
            "open": round(float(b.get("open", b.get("close", 0))), 2),
            "high": round(float(b.get("high", b.get("close", 0))), 2),
            "low": round(float(b.get("low", b.get("close", 0))), 2),
            "close": round(float(b.get("close", b.get("price", 0))), 2),
        })
    return {"bars": bars, "source": source}
