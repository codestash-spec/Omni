from dataclasses import dataclass
from typing import List


@dataclass
class TickerData:
    symbol: str
    last_price: float
    pct_change: float
    volume: float
    bid: float
    ask: float

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)


@dataclass
class Candle:
    open_time: int  # ms
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    symbol: str
    price: float
    qty: float
    side: str  # "Buy" or "Sell"
    ts: int  # ms


@dataclass
class OrderBookLevel:
    price: float
    size: float


@dataclass
class OrderBookSnapshot:
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    ts: int
