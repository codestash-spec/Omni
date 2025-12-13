from dataclasses import dataclass


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
class TradeData:
    symbol: str
    price: float
    qty: float
    side: str  # "Buy" or "Sell"
    ts: int


@dataclass
class CandleData:
    symbol: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
