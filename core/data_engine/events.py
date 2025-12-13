from dataclasses import dataclass
from typing import List, Tuple

from data_engine.models import Candle, Trade, OrderBookSnapshot


@dataclass
class SymbolChanged:
    symbol: str


@dataclass
class TimeframeChanged:
    timeframe: str


@dataclass
class CandleHistory:
    symbol: str
    timeframe: str
    candles: List[Candle]


@dataclass
class CandleUpdate:
    symbol: str
    timeframe: str
    candle: Candle
    closed: bool


@dataclass
class TradeEvent:
    trade: Trade


@dataclass
class DepthSnapshotEvent:
    symbol: str
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]
    last_update_id: int


@dataclass
class DepthUpdateEvent:
    symbol: str
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]
    last_update_id: int


@dataclass
class TickersEvent:
    tickers: list

