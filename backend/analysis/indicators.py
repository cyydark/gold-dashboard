"""Technical indicators calculation with plain explanations."""
import ta
import pandas as pd
from backend.data.models import Indicators, OHLCV


def calc_ma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def calc_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    series = pd.Series(closes)
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 2) if pd.notna(val) else None


def calc_macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float | None, float | None, float | None]:
    if len(closes) < slow:
        return None, None, None
    series = pd.Series(closes)
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    hist = macd_line - signal_line
    return (
        round(float(macd_line.iloc[-1]), 4) if pd.notna(macd_line.iloc[-1]) else None,
        round(float(signal_line.iloc[-1]), 4) if pd.notna(signal_line.iloc[-1]) else None,
        round(float(hist.iloc[-1]), 4) if pd.notna(hist.iloc[-1]) else None,
    )


def build_signal(price: float, ma5: float | None, ma20: float | None,
                 ma60: float | None, rsi: float | None) -> str:
    """Generate a plain-language signal."""
    signals = []

    if ma5 and ma20 and price > ma5 > ma20:
        signals.append("📈 短期强势：价格 > MA5 > MA20，多头排列")
    elif ma5 and ma20 and price < ma5 < ma20:
        signals.append("📉 短期弱势：价格 < MA5 < MA20，空头排列")

    if ma5 and ma20 and ma60:
        if ma5 > ma20 > ma60:
            signals.append("均线金叉，多头格局")
        elif ma5 < ma20 < ma60:
            signals.append("均线死叉，空头格局")

    if rsi:
        if rsi > 70:
            signals.append(f"⚠️ RSI={rsi} 处于超买区（>70），注意回调风险")
        elif rsi < 30:
            signals.append(f"🟢 RSI={rsi} 处于超卖区（<30），注意反弹机会")
        else:
            signals.append(f"RSI={rsi} 处于中性区间（30-70）")

    return "；".join(signals) if signals else "暂无明确信号"


def calc_indicators(ohlcv: list[OHLCV], symbol: str) -> Indicators:
    closes = [c.close for c in ohlcv]
    ma5 = calc_ma(closes, 5)
    ma10 = calc_ma(closes, 10)
    ma20 = calc_ma(closes, 20)
    ma60 = calc_ma(closes, 60) if len(closes) >= 60 else None
    rsi = calc_rsi(closes)
    macd_val, macd_sig, macd_hist = calc_macd(closes)
    current_price = closes[-1] if closes else 0
    signal = build_signal(current_price, ma5, ma20, ma60, rsi)

    return Indicators(
        symbol=symbol,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        rsi=rsi,
        macd=macd_val,
        macd_signal=macd_sig,
        macd_hist=macd_hist,
        signal=signal,
    )
