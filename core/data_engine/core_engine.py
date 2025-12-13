import logging
import threading
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from core.data_engine.cache_manager import CacheManager
from core.data_engine.events import (
    CandleHistory,
    CandleUpdate,
    DepthSnapshotEvent,
    DepthUpdateEvent,
    SymbolChanged,
    TickersEvent,
    TimeframeChanged,
    TradeEvent,
)
from core.data_engine.symbol_state import SymbolState
from core.data_engine.timeframe_state import TimeframeState
from core.data_engine.providers.binance_provider import BinanceProvider
from data_engine.models import Candle, Trade


class CoreDataEngine(QObject):
    """
    Unified data gateway for UI. Single source of truth for symbol/timeframe data streams.
    """

    symbol_changed = Signal(object)  # SymbolChanged
    timeframe_changed = Signal(object)  # TimeframeChanged
    candle_history = Signal(object)  # CandleHistory
    candle_update = Signal(object)  # CandleUpdate
    trade = Signal(object)  # TradeEvent
    depth_snapshot = Signal(object)  # DepthSnapshotEvent
    depth_update = Signal(object)  # DepthUpdateEvent
    tickers = Signal(object)  # TickersEvent
    status = Signal(str)

    def __init__(self, parent=None, initial_symbol: str = "BTCUSDT", initial_timeframe: str = "1m"):
        super().__init__(parent)
        self._logger = logging.getLogger(__name__)
        self._symbol_state = SymbolState(initial_symbol)
        self._timeframe_state = TimeframeState(initial_timeframe)
        self._cache = CacheManager()
        self._provider: Optional[BinanceProvider] = None
        self._lock = threading.Lock()
        self._started = False

    # --- Public API ---
    def start(self):
        with self._lock:
            if self._started:
                return
            self._started = True
        self._logger.info("CoreDataEngine starting for %s %s", self._symbol_state.symbol, self._timeframe_state.timeframe)
        try:
            self._provider = BinanceProvider(
                on_history=self._on_history,
                on_candle=self._on_candle_update,
                on_trade=self._on_trade,
                on_depth_snapshot=self._on_depth_snapshot,
                on_depth_update=self._on_depth_update,
                on_tickers=self._on_tickers,
                on_status=self._on_status,
            )
            self._provider.start(self._symbol_state.symbol, self._timeframe_state.timeframe)
            self.symbol_changed.emit(SymbolChanged(symbol=self._symbol_state.symbol))
            self.timeframe_changed.emit(TimeframeChanged(timeframe=self._timeframe_state.timeframe))
            self.status.emit("Connected")
            self._logger.info("CoreDataEngine started successfully")
        except Exception as e:
            self._logger.error("Failed to start CoreDataEngine: %s", e)
            self.status.emit(f"Error: {str(e)}")
            with self._lock:
                self._started = False

    def stop(self):
        with self._lock:
            self._started = False
        if self._provider:
            self._provider.stop()
            self._provider = None

    def set_symbol(self, symbol: str):
        prev = self._symbol_state.symbol
        new_sym = self._symbol_state.set(symbol)
        if new_sym == prev:
            return
        self._logger.info("CoreDataEngine symbol -> %s", new_sym)
        self.symbol_changed.emit(SymbolChanged(symbol=new_sym))
        if self._provider:
            self._provider.set_symbol_timeframe(new_sym, self._timeframe_state.timeframe)

    def set_timeframe(self, timeframe: str):
        prev = self._timeframe_state.timeframe
        new_tf = self._timeframe_state.set(timeframe)
        if new_tf == prev:
            return
        self._logger.info("CoreDataEngine timeframe -> %s", new_tf)
        self.timeframe_changed.emit(TimeframeChanged(timeframe=new_tf))
        if self._provider:
            self._provider.set_symbol_timeframe(self._symbol_state.symbol, new_tf)

    # --- Callbacks from provider (executed on provider thread; Qt will queue signals) ---
    def _on_history(self, symbol: str, timeframe: str, candles: list[Candle]):
        self._cache.set_history(symbol, timeframe, candles)
        self.candle_history.emit(CandleHistory(symbol=symbol.upper(), timeframe=timeframe, candles=candles))

    def _on_candle_update(self, symbol: str, timeframe: str, candle: Candle, closed: bool):
        self._cache.append_candle(symbol, timeframe, candle, closed)
        self.candle_update.emit(CandleUpdate(symbol=symbol.upper(), timeframe=timeframe, candle=candle, closed=closed))

    def _on_trade(self, symbol: str, trade: Trade):
        self._cache.append_trade(symbol, trade)
        self.trade.emit(TradeEvent(trade=trade))

    def _on_depth_snapshot(self, evt: DepthSnapshotEvent):
        self._cache.set_depth(evt.symbol, evt.bids, evt.asks, evt.last_update_id)
        self.depth_snapshot.emit(evt)

    def _on_depth_update(self, evt: DepthUpdateEvent):
        self._cache.set_depth(evt.symbol, evt.bids, evt.asks, evt.last_update_id)
        self.depth_update.emit(evt)

    def _on_tickers(self, payload):
        self.tickers.emit(TickersEvent(tickers=payload))

    def _on_status(self, status: str):
        self.status.emit(status)
