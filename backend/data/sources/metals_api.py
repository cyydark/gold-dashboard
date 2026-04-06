"""LBMA Gold Price (XAU/USD) via Metals-API.

数据源: Metals-API (https://metals-api.com/)
品种: XAU/USD — LBMA Gold Price AM/PM 现货基准
单位: 美元/盎司 (USD/oz)
免费额度: 2500次/月
"""
import calendar
import logging
import os
from datetime import date, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://metals-api.com/api"
_API_KEY = os.environ.get("METALS_API_KEY")


def fetch_xauusd_realtime() -> dict | None:
    """Fetch LBMA Gold Price (XAU/USD) spot price from Metals-API.

    Returns:
        {
            "price": float,   # current LBMA Gold price USD/oz
            "change": float,  # 24h change amount (estimated from previous day close)
            "pct": float,     # 24h change percentage
            "open": float,    # estimated from latest close (Metals-API realtime has no OHLC)
            "high": float,    # estimated from latest close
            "low": float,     # estimated from latest close
        }
        or None if the API key is not set or the request fails.
    """
    if not _API_KEY:
        logger.info("METALS_API_KEY not set, skipping Metals-API realtime fetch")
        return None

    url = f"{_BASE_URL}/latest"
    params = {
        "api_key": _API_KEY,
        "base": "XAU",
        "currency": "USD",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        price = float(data.get("price", 0))
        if price <= 0:
            logger.warning("Metals-API returned invalid price: %s", data)
            return None

        # Metals-API realtime endpoint does not provide OHLC or previous close.
        # Estimate change/pct from the previous day's timeseries close.
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        today_str = date.today().isoformat()

        hist = _fetch_timeseries_impl(yesterday, today_str)
        prev_close = None
        if hist:
            prev_close = hist[0].get("close")

        change = 0.0
        pct = 0.0
        if prev_close and prev_close > 0:
            change = round(price - prev_close, 2)
            pct = round((change / prev_close) * 100, 2)

        return {
            "price": round(price, 2),
            "change": change,
            "pct": pct,
            "open": round(price, 2),
            "high": round(price, 2),
            "low": round(price, 2),
        }
    except requests.RequestException as e:
        logger.warning("Metals-API realtime request failed: %s", e)
        return None
    except (ValueError, TypeError) as e:
        logger.warning("Metals-API realtime parse error: %s", e)
        return None


def fetch_xauusd_history(days: int = 30) -> list[dict] | None:
    """Fetch LBMA Gold Price (XAU/USD) daily history from Metals-API.

    Args:
        days: Number of past calendar days to fetch (default 30).

    Returns:
        List of daily bars [{time, open, high, low, close, volume, change, pct}, ...]
        sorted oldest-first, or None on error / missing API key.
    """
    if not _API_KEY:
        logger.info("METALS_API_KEY not set, skipping Metals-API history fetch")
        return None

    end = date.today()
    start = end - timedelta(days=days)
    return _fetch_timeseries_impl(start.isoformat(), end.isoformat())


def _fetch_timeseries_impl(start_date: str, end_date: str) -> list[dict] | None:
    """Internal: fetch timeseries from Metals-API and normalise to OHLCV records.

    Metals-API timeseries returns a ``rates`` dict keyed by ISO date strings.
    Each value is a single float (XAU→USD conversion factor, i.e. price in USD/oz).

    Returns:
        List of normalised bars, oldest first, or None on failure.
    """
    url = f"{_BASE_URL}/timeseries"
    params = {
        "api_key": _API_KEY,
        "base": "XAU",
        "currency": "USD",
        "start_date": start_date,
        "end_date": end_date,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        rates: dict[str, float] = data.get("rates", {})
        if not rates:
            logger.warning("Metals-API timeseries returned no rates: %s", data)
            return None

        records: list[dict] = []
        # Build a sorted list of (date_str, price) for change/pct calculation
        sorted_items = sorted(rates.items(), key=lambda x: x[0])

        for idx, (ds, price) in enumerate(sorted_items):
            price = float(price)
            if price <= 0:
                continue

            prev_price = float(sorted_items[idx - 1][1]) if idx > 0 else price
            change = round(price - prev_price, 2)
            pct = 0.0
            if idx > 0 and prev_price > 0:
                pct = round((change / prev_price) * 100, 2)

            # Parse date → midnight UTC timestamp
            dt = date.fromisoformat(ds)
            ts = calendar.timegm(dt.timetuple())

            records.append({
                "time":    ts,
                "open":    round(price, 2),
                "high":    round(price, 2),
                "low":     round(price, 2),
                "close":   round(price, 2),
                "volume":  0.0,          # Metals-API provides no volume
                "change":  change,
                "pct":     pct,
            })

        return records if records else None
    except requests.RequestException as e:
        logger.warning("Metals-API timeseries request failed: %s", e)
        return None
    except (ValueError, TypeError, KeyError) as e:
        logger.warning("Metals-API timeseries parse error: %s", e)
        return None
