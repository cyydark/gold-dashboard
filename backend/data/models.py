"""Pydantic data models."""
from pydantic import BaseModel
from typing import Optional


class OHLCV(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int


class Indicators(BaseModel):
    symbol: str
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    signal: str = ""   # 通俗信号


class AlertRule(BaseModel):
    id: Optional[int] = None
    symbol: str
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    condition: str = "cross"  # cross | above | below
    active: bool = True


class AlertCreate(BaseModel):
    symbol: str
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    condition: str = "cross"
