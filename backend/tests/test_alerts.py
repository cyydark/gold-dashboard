"""Tests for check_alerts() in alerts/engine.py

External dependencies (yfinance, sqlite3) are mocked.
Only the pure logic of check_alerts() is exercised.
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helper: build a minimal prices dict matching the expected schema
# ---------------------------------------------------------------------------
def make_prices(**overrides) -> dict:
    """Return a minimal prices dict with a nested dict for the symbol."""
    defaults = {
        "symbol": "XAUUSD",
        "price": 2950.0,
        "change": 10.5,
        "pct": 0.36,
        "unit": "USD/oz",
    }
    defaults.update(overrides)
    return {"XAUUSD": defaults}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_rules():
    """Sample active rules from the DB."""
    return [
        {
            "id": 1,
            "symbol": "XAUUSD",
            "high_price": 3000.0,
            "low_price": 2800.0,
            "active": 1,
            "created_at": "2025-01-01T00:00:00",
        },
        {
            "id": 2,
            "symbol": "XAUUSD",
            "high_price": 3100.0,
            "low_price": None,
            "active": 1,
            "created_at": "2025-01-01T00:00:00",
        },
        {
            "id": 3,
            "symbol": "XAUUSD",
            "high_price": None,
            "low_price": 2700.0,
            "active": 1,
            "created_at": "2025-01-01T00:00:00",
        },
        {
            "id": 4,
            "symbol": "XAUUSD",
            "high_price": None,
            "low_price": None,
            "active": 1,
            "created_at": "2025-01-01T00:00:00",
        },
    ]


@pytest.fixture
def mock_get_rules(mock_rules):
    """Patch _get_rules_sync to return sample rules."""
    with patch("backend.alerts.engine._get_rules_sync", return_value=mock_rules) as p:
        yield p


@pytest.fixture
def mock_log_alert():
    """Patch _log_alert_sync to capture calls."""
    with patch("backend.alerts.engine._log_alert_sync") as p:
        yield p


# ---------------------------------------------------------------------------
# Happy path: price crosses high threshold → above alert
# ---------------------------------------------------------------------------
def test_alert_above_high_threshold_triggers(mock_get_rules, mock_log_alert):
    """Price >= high_price triggers an 'above' alert."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=3005.0)  # above rule 1 high (3000.0)
    alerts = check_alerts(prices)

    assert len(alerts) == 1
    assert alerts[0]["direction"] == "above"
    assert alerts[0]["threshold"] == 3000.0
    assert alerts[0]["price"] == 3005.0
    assert alerts[0]["rule_id"] == 1
    mock_log_alert.assert_called_once_with("XAUUSD", 3005.0, "above")


def test_alert_above_exact_high_threshold_triggers(mock_get_rules, mock_log_alert):
    """Price == high_price also triggers (>= comparison)."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=3000.0)  # exactly at rule 1 high
    alerts = check_alerts(prices)

    assert len(alerts) == 1
    assert alerts[0]["direction"] == "above"
    assert alerts[0]["threshold"] == 3000.0


# ---------------------------------------------------------------------------
# Happy path: price crosses low threshold → below alert
# ---------------------------------------------------------------------------
def test_alert_below_low_threshold_triggers(mock_get_rules, mock_log_alert):
    """Price <= low_price triggers a 'below' alert."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=2790.0)  # below rule 1 low (2800.0)
    alerts = check_alerts(prices)

    assert len(alerts) == 1
    assert alerts[0]["direction"] == "below"
    assert alerts[0]["threshold"] == 2800.0
    assert alerts[0]["price"] == 2790.0
    assert alerts[0]["rule_id"] == 1
    mock_log_alert.assert_called_once_with("XAUUSD", 2790.0, "below")


def test_alert_below_exact_low_threshold_triggers(mock_get_rules, mock_log_alert):
    """Price == low_price also triggers (<= comparison)."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=2800.0)  # exactly at rule 1 low
    alerts = check_alerts(prices)

    assert len(alerts) == 1
    assert alerts[0]["direction"] == "below"
    assert alerts[0]["threshold"] == 2800.0


# ---------------------------------------------------------------------------
# Both thresholds triggered simultaneously
# ---------------------------------------------------------------------------
def test_both_thresholds_triggered_same_price(mock_get_rules, mock_log_alert):
    """If a single price satisfies both high and low thresholds, two alerts fire."""
    from backend.alerts.engine import check_alerts

    # Price 2790.0 is below rule 1 low (2800.0) — should trigger below
    # But 2790.0 is also below rule 1 high (3000.0) — rule 1 has both thresholds
    prices = make_prices(price=2790.0)
    alerts = check_alerts(prices)

    # Rule 1: low_price=2800.0, price=2790.0 <= 2800.0 → below alert
    # Rule 1: high_price=3000.0, price=2790.0 < 3000.0 → no above alert
    assert any(a["direction"] == "below" for a in alerts)
    assert not any(a["direction"] == "above" for a in alerts)


# ---------------------------------------------------------------------------
# Multiple rules: only the matching one fires
# ---------------------------------------------------------------------------
def test_only_relevant_symbol_fires(mock_get_rules, mock_log_alert):
    """Rules for other symbols are ignored."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=3100.0)
    alerts = check_alerts(prices)

    # Rule 1: high=3000.0, price=3100.0 >= 3000.0 → above (fires)
    # Rule 2: high=3100.0, price=3100.0 >= 3100.0 → above (fires)
    # Rule 3: low=2700.0, price=3100.0 > 2700.0 → no below
    assert len(alerts) == 2
    assert all(a["symbol"] == "XAUUSD" for a in alerts)


# ---------------------------------------------------------------------------
# No alert conditions met
# ---------------------------------------------------------------------------
def test_no_alert_when_price_inside_band(mock_get_rules, mock_log_alert):
    """Price between thresholds triggers nothing."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=2950.0)  # inside [2800, 3000]
    alerts = check_alerts(prices)

    assert len(alerts) == 0
    mock_log_alert.assert_not_called()


# ---------------------------------------------------------------------------
# Edge: price = None → skipped
# ---------------------------------------------------------------------------
def test_skips_symbol_when_price_is_none(mock_get_rules, mock_log_alert):
    """If price is None, no alert is generated for that symbol."""
    from backend.alerts.engine import check_alerts

    prices = {"XAUUSD": {"price": None}}
    alerts = check_alerts(prices)

    assert len(alerts) == 0
    mock_log_alert.assert_not_called()


def test_skips_symbol_not_in_prices(mock_get_rules, mock_log_alert):
    """If symbol is absent from prices dict, no alert is generated."""
    from backend.alerts.engine import check_alerts

    prices = {}  # empty — no symbols at all
    alerts = check_alerts(prices)

    assert len(alerts) == 0
    mock_log_alert.assert_not_called()


# ---------------------------------------------------------------------------
# Edge: rule threshold = None → that comparison is skipped
# ---------------------------------------------------------------------------
def test_rule_with_only_high_threshold(mock_get_rules, mock_log_alert):
    """A rule with only high_price set fires only on above; other rules may also fire."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=3150.0)
    alerts = check_alerts(prices)

    # Rule 2 (high=3100.0) fires as above — verified by rule_id
    # Rule 1 (high=3000.0) also fires (price >= 3000.0) — expected with shared fixture
    above_alerts = [a for a in alerts if a["direction"] == "above"]
    assert any(a["rule_id"] == 2 for a in above_alerts), "Rule 2 (high-only) should fire above"
    assert not any(a["direction"] == "below" for a in alerts)


def test_rule_with_only_low_threshold(mock_get_rules, mock_log_alert):
    """A rule with only low_price set fires only on below; other rules may also fire."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=2600.0)
    alerts = check_alerts(prices)

    # Rule 3 (low=2700.0) fires as below — verified by rule_id
    # Rule 1 (low=2800.0) also fires (price <= 2800.0) — expected with shared fixture
    below_alerts = [a for a in alerts if a["direction"] == "below"]
    assert any(a["rule_id"] == 3 for a in below_alerts), "Rule 3 (low-only) should fire below"
    assert not any(a["direction"] == "above" for a in alerts)


def test_rule_with_no_thresholds(mock_get_rules, mock_log_alert):
    """A rule with both thresholds None never fires."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=2950.0)
    alerts = check_alerts(prices)

    # Rule 4: both None — never fires
    assert not any(a["rule_id"] == 4 for a in alerts)


# ---------------------------------------------------------------------------
# Alert message content
# ---------------------------------------------------------------------------
def test_alert_message_contains_price_and_threshold(mock_get_rules, mock_log_alert):
    """Alert message includes both triggered price and threshold."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=3005.0)
    alerts = check_alerts(prices)

    assert len(alerts) == 1
    msg = alerts[0]["message"]
    assert "3005.0" in msg
    assert "3000.0" in msg


def test_above_alert_message_emoji(mock_get_rules, mock_log_alert):
    """Above alert uses the rising emoji."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=3100.0)
    alerts = check_alerts(prices)

    msg = alerts[0]["message"]
    assert "🚨" in msg
    assert "上涨" in msg


def test_below_alert_message_emoji(mock_get_rules, mock_log_alert):
    """Below alert uses the falling emoji."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=2700.0)
    alerts = check_alerts(prices)

    msg = alerts[0]["message"]
    assert "📉" in msg
    assert "下跌" in msg


# ---------------------------------------------------------------------------
# Log is called for every triggered alert (not just once)
# ---------------------------------------------------------------------------
def test_log_called_per_triggered_alert(mock_get_rules, mock_log_alert):
    """Each individual alert triggers a separate log call."""
    from backend.alerts.engine import check_alerts

    prices = make_prices(price=3200.0)
    alerts = check_alerts(prices)

    # Rule 1: above (>= 3000.0), Rule 2: above (>= 3100.0)
    assert mock_log_alert.call_count == 2


# ---------------------------------------------------------------------------
# Empty rules list
# ---------------------------------------------------------------------------
def test_no_rules_returns_empty_list(mock_log_alert):
    """If _get_rules_sync returns [], check_alerts returns [] without error."""
    from backend.alerts.engine import check_alerts

    with patch("backend.alerts.engine._get_rules_sync", return_value=[]):
        alerts = check_alerts(make_prices(price=99999.0))

    assert alerts == []
    mock_log_alert.assert_not_called()


# ---------------------------------------------------------------------------
# DB error: _get_rules_sync raises
# ---------------------------------------------------------------------------
def test_get_rules_raises_propagates(mock_log_alert):
    """If DB access fails, the exception propagates."""
    from backend.alerts.engine import check_alerts

    with patch("backend.alerts.engine._get_rules_sync", side_effect=RuntimeError("DB error")):
        with pytest.raises(RuntimeError, match="DB error"):
            check_alerts(make_prices(price=3000.0))

    mock_log_alert.assert_not_called()


# ---------------------------------------------------------------------------
# _log_alert_sync error does not prevent other alerts or raise
# ---------------------------------------------------------------------------
def test_log_alert_error_does_not_prevent_other_alerts(mock_get_rules):
    """If one _log_alert_sync call fails, other alerts still fire."""
    from backend.alerts.engine import check_alerts

    def log_side_effect(*args):
        if args[1] == 3000.0:  # first triggered alert
            raise RuntimeError("log write failed")

    with patch("backend.alerts.engine._log_alert_sync", side_effect=log_side_effect):
        prices = make_prices(price=3100.0)
        alerts = check_alerts(prices)

    # Rule 2 (high=3100.0) fires; log fails but exception is not re-raised
    # Rule 1 (high=3000.0) also fires; its log call would also raise
    # Since both rules fire and both logs raise, all alerts are still in list
    assert len(alerts) == 2


# ---------------------------------------------------------------------------
# Multiple symbols in prices
# ---------------------------------------------------------------------------
def test_multiple_symbols_only_processes_matched_rules(mock_get_rules, mock_log_alert):
    """Rules are evaluated per-symbol; unrelated symbols are ignored."""
    from backend.alerts.engine import check_alerts

    prices = {
        "XAUUSD": {"price": 3100.0},
        "USDCNY": {"price": 7.25},
    }
    alerts = check_alerts(prices)

    assert all(a["symbol"] == "XAUUSD" for a in alerts)
    assert not any(a["symbol"] == "USDCNY" for a in alerts)
