from collections import deque
from typing import Deque, List, Dict


class ChartEngine:
    """
    Lightweight candle store with incremental updates and a fixed window.
    """

    def __init__(self, max_candles: int = 300):
        self.max_candles = max_candles
        self._candles: Deque[Dict] = deque(maxlen=max_candles)

    def set_history(self, candles: List[Dict]):
        self._candles.clear()
        for c in candles[-self.max_candles :]:
            self._candles.append(c)

    def get_visible_candles(self) -> List[Dict]:
        return list(self._candles)

    def append_candle(self, candle: Dict):
        self._candles.append(candle)

    def update_last_candle(self, candle: Dict):
        if self._candles:
            self._candles.pop()
        self._candles.append(candle)
