from collections import deque
from typing import Deque, Dict, List, Tuple

from core.data_engine.models import Candle, Trade



class CacheManager:
    """
    In-memory cache keyed by (symbol, timeframe). Keeps recent candles/trades/depth snapshots.
    Prepared for disk persistence in future iterations.
    """

    def __init__(self, max_candles: int = 1200, max_trades: int = 2000):
        self._max_candles = max_candles
        self._max_trades = max_trades
        self._candles: Dict[Tuple[str, str], Deque[Candle]] = {}
        self._trades: Dict[str, Deque[Trade]] = {}
        self._depth: Dict[str, Dict] = {}

    def set_history(self, symbol: str, timeframe: str, candles: List[Candle]):
        key = (symbol.upper(), timeframe)
        dq: Deque[Candle] = deque(maxlen=self._max_candles)
        for c in candles[-self._max_candles :]:
            dq.append(c)
        self._candles[key] = dq

    def append_candle(self, symbol: str, timeframe: str, candle: Candle, closed: bool):
        key = (symbol.upper(), timeframe)
        dq = self._candles.get(key)
        if not dq:
            dq = deque(maxlen=self._max_candles)
            self._candles[key] = dq
        if closed:
            if dq and candle.open_time <= dq[-1].open_time:
                dq[-1] = candle
            else:
                dq.append(candle)
        else:
            if dq:
                dq[-1] = candle
            else:
                dq.append(candle)

    def get_history(self, symbol: str, timeframe: str) -> List[Candle]:
        key = (symbol.upper(), timeframe)
        if key not in self._candles:
            return []
        return list(self._candles[key])

    def append_trade(self, symbol: str, trade: Trade):
        key = symbol.upper()
        dq = self._trades.get(key)
        if not dq:
            dq = deque(maxlen=self._max_trades)
            self._trades[key] = dq
        dq.append(trade)

    def get_trades(self, symbol: str) -> List[Trade]:
        key = symbol.upper()
        if key not in self._trades:
            return []
        return list(self._trades[key])

    def set_depth(self, symbol: str, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]], last_update_id: int):
        self._depth[symbol.upper()] = {
            "bids": bids,
            "asks": asks,
            "last_update_id": last_update_id,
        }

    def get_depth(self, symbol: str):
        return self._depth.get(symbol.upper())
