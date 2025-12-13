from dataclasses import dataclass
from typing import List

from data_engine.models import Candle, Trade


@dataclass
class HistoryLoaded:
    symbol: str
    timeframe: str
    candles: List[Candle]


@dataclass
class CandleUpdated:
    symbol: str
    timeframe: str
    candle: Candle
    closed: bool


@dataclass
class TradeReceived:
    trade: Trade
