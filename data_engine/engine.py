import concurrent.futures
import logging
import threading
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from data_engine.cache import DataCache
from data_engine.events import CandleUpdated, HistoryLoaded, TradeReceived
from data_engine.historical_loader import HistoricalDataLoader
from data_engine.models import Candle
from data_engine.realtime_stream import RealtimeStream


class DataEngine(QObject):
    history_loaded = Signal(object)  # HistoryLoaded
    candle_updated = Signal(object)  # CandleUpdated
    trade_received = Signal(object)  # TradeReceived

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache = DataCache()
        self._loader = HistoricalDataLoader()
        self._stream: Optional[RealtimeStream] = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._symbol = "BTCUSDT"
        self._timeframe = "1m"
        self._future: Optional[concurrent.futures.Future] = None
        self._history_limit = 1000
        self._lookback_days = 365
        self._max_candles = 5000

    def start(self, symbol: str, timeframe: str = "1m"):
        with self._lock:
            self.stop()
            self._symbol = symbol.upper()
            self._timeframe = timeframe
            cached = self._cache.get(self._symbol, timeframe)
            if cached:
                self._logger.debug("Cache hit for %s %s", self._symbol, timeframe)
                self.history_loaded.emit(HistoryLoaded(symbol=self._symbol, timeframe=timeframe, candles=cached))
            self._future = self._executor.submit(self._load_history_and_stream)

    def stop(self):
        if self._stream:
            self._stream.stop()
        if self._future and not self._future.done():
            self._future.cancel()

    def _load_history_and_stream(self):
        try:
            self._logger.info(
                "Loading history for %s %s (limit=%d, lookback_days=%d, max_candles=%d)",
                self._symbol,
                self._timeframe,
                self._history_limit,
                self._lookback_days,
                self._max_candles,
            )
            candles = self._loader.load_ohlc(
                self._symbol,
                self._timeframe,
                limit=self._history_limit,
                lookback_days=self._lookback_days,
                max_candles=self._max_candles,
            )
            self._logger.info(
                "History loaded for %s %s -> %d candles (first=%s last=%s)",
                self._symbol,
                self._timeframe,
                len(candles),
                f"{candles[0].close:.2f}" if candles else "n/a",
                f"{candles[-1].close:.2f}" if candles else "n/a",
            )
            self._cache.set(self._symbol, self._timeframe, candles)
            self.history_loaded.emit(HistoryLoaded(symbol=self._symbol, timeframe=self._timeframe, candles=candles))
        except Exception:
            self._logger.exception("Failed to load history for %s %s", self._symbol, self._timeframe)
        self._stream = RealtimeStream(self._handle_candle, self._handle_trade)
        self._stream.start(self._symbol, self._timeframe)

    def _handle_candle(self, event: CandleUpdated):
        self.candle_updated.emit(event)

    def _handle_trade(self, event: TradeReceived):
        self.trade_received.emit(event)
