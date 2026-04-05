"""Server-Sent Events (SSE) for real-time price streaming."""
import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.data.db import get_latest_price_bar, get_latest_usdcny
from backend.data.sources.binance_kline import fetch_xauusd_realtime

from backend.data import constants as c

BEIJING_TZ = timezone(timedelta(hours=8))
router = APIRouter(tags=["sse"])


def _format_price(bar: dict | None, symbol: str, now_ts: int) -> dict | None:
    """Convert a price bar to price card format.

    change/pct come from the data source (not computed from close-open).
    Falls back to computing from close-open only when bar has no change/pct.
    """
    if not bar:
        return None
    ts = bar["ts"]
    price = round(bar["price"], 2)
    open_px = round(bar["open"], 2)
    names = {"XAUUSD": ("国际黄金 XAU/USD", "USD/oz"), "AU9999": ("国内黄金 AU9999", "CNY/g")}
    name, unit = names.get(symbol, (symbol, ""))

    # Use stored change/pct from data source when available; otherwise compute
    stored_change = bar.get("change")
    stored_pct = bar.get("pct")
    if stored_change is not None and stored_pct is not None:
        change_val = round(float(stored_change), 2)
        pct_val = round(float(stored_pct), 2)
    else:
        change_val = round(price - open_px, 2)
        pct_val = round((price - open_px) / open_px * 100, 2) if open_px else 0

    return {
        "symbol": symbol,
        "name": name,
        "price": price,
        "ts": ts,
        "now_ts": now_ts,
        "change": change_val,
        "pct": pct_val,
        "open": open_px,
        "high": round(bar["high"], 2),
        "low": round(bar["low"], 2),
        "unit": unit,
        "updated_at": datetime.fromtimestamp(now_ts, BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }


def _format_fx(fx: dict | None) -> dict | None:
    """Format USDCNY from DB (with OHLC)."""
    if not fx:
        return None
    return {
        "symbol": "USDCNY",
        "name": "人民币兑美元 CNY/USD",
        "price": round(fx["price"], 4),
        "change": round(fx.get("change", 0), 4),
        "pct": round(fx.get("pct", 0), 2),
        "open": round(fx.get("open", fx["price"]), 4),
        "high": round(fx.get("high", fx["price"]), 4),
        "low": round(fx.get("low", fx["price"]), 4),
        "unit": "CNY/USD",
        "updated_at": datetime.fromtimestamp(fx["ts"], BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
    }


async def price_generator():
    """Yield SSE events with current prices every PRICE_INTERVAL seconds."""
    while True:
        now_ts = int(time.time())

        # XAUUSD: Binance ticker — 实时涨跌
        xau_rt = await asyncio.to_thread(fetch_xauusd_realtime)
        if xau_rt:
            payload_xau = {
                "symbol": "XAUUSD",
                "name": "国际黄金 XAU/USD",
                "price": xau_rt["price"],
                "ts": now_ts,
                "now_ts": now_ts,
                "change": xau_rt["change"],
                "pct": xau_rt["pct"],
                "open": xau_rt["open"],
                "high": xau_rt["high"],
                "low": xau_rt["low"],
                "unit": "USD/oz",
                "updated_at": datetime.fromtimestamp(now_ts, BEIJING_TZ).strftime("%m月%d日 %H:%M:%S 北京时间"),
            }
        else:
            xau_bar = await get_latest_price_bar("XAUUSD")
            payload_xau = _format_price(xau_bar, "XAUUSD", now_ts) if xau_bar else None

        # AU9999 / USDCNY: 从 DB 读（已含涨跌）
        au_bar = await get_latest_price_bar("AU9999")
        fx_bar = await get_latest_usdcny()

        payload = {}
        if payload_xau:
            payload["XAUUSD"] = payload_xau
        if au_bar:
            payload["AU9999"] = _format_price(au_bar, "AU9999", now_ts)
        if fx_bar:
            payload["USDCNY"] = _format_fx(fx_bar)

        if payload:
            payload["updated_at"] = (
                payload.get("XAUUSD", {}).get("updated_at", "") or
                payload.get("AU9999", {}).get("updated_at", "") or
                payload.get("USDCNY", {}).get("updated_at", "")
            )
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(c.SSE_INTERVAL)


@router.get("/stream")
async def stream_prices():
    return StreamingResponse(
        price_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
