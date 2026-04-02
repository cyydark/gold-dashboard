"""Alert engine: checks prices against rules (sync, runs in thread pool)."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "alerts.db")


def _get_rules_sync():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM alert_rules WHERE active = 1 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _log_alert_sync(symbol, price, direction):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO alert_history (symbol, price, direction) VALUES (?, ?, ?)",
        (symbol, price, direction),
    )
    conn.commit()
    conn.close()


def check_alerts(prices: dict) -> list[dict]:
    """Check prices against all active rules, return triggered alerts."""
    rules = _get_rules_sync()
    triggered = []

    for rule in rules:
        symbol = rule["symbol"]
        if symbol not in prices:
            continue

        price = prices[symbol].get("price")
        if price is None:
            continue

        if rule["high_price"] is not None and price >= rule["high_price"]:
            msg = f"🚨 {symbol} 价格上涨至 {price}，突破高价预警 {rule['high_price']}"
            _log_alert_sync(symbol, price, "above")
            triggered.append({
                "rule_id": rule["id"], "symbol": symbol,
                "direction": "above", "threshold": rule["high_price"],
                "price": price, "message": msg,
            })

        if rule["low_price"] is not None and price <= rule["low_price"]:
            msg = f"📉 {symbol} 价格下跌至 {price}，突破低价预警 {rule['low_price']}"
            _log_alert_sync(symbol, price, "below")
            triggered.append({
                "rule_id": rule["id"], "symbol": symbol,
                "direction": "below", "threshold": rule["low_price"],
                "price": price, "message": msg,
            })

    return triggered
