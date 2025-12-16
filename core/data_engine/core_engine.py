import logging
import threading
from typing import Optional

from PySide6.QtCore import QObject, Signal

# ==========================================================
# CACHE LOCAL
# ==========================================================

from core.data_engine.cache_manager import CacheManager

# ==========================================================
# EVENTOS TIPADOS
# ==========================================================

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

# ==========================================================
# ESTADOS THREAD-SAFE
# ==========================================================

from core.data_engine.symbol_state import SymbolState
from core.data_engine.timeframe_state import TimeframeState

# ==========================================================
# PROVIDER
# ==========================================================

from core.data_engine.providers.binance_provider import BinanceProvider

# ==========================================================
# MODELOS
# ==========================================================

from core.data_engine.models import Candle, Trade


class CoreDataEngine(QObject):
    """
    CORE DATA ENGINE (VERSÃO FINAL)

    Responsabilidades:
    - Single Source of Truth de dados de mercado
    - Mediação entre Provider (Binance) e UI
    - Gestão de símbolo / timeframe
    - Cache consistente (candles, trades, depth)
    """

    # ------------------------------------------------------
    # SINAIS PÚBLICOS (QT)
    # ------------------------------------------------------

    symbol_changed = Signal(object)      # SymbolChanged
    timeframe_changed = Signal(object)   # TimeframeChanged

    candle_history = Signal(object)      # CandleHistory
    candle_update = Signal(object)       # CandleUpdate

    trade = Signal(object)               # TradeEvent

    depth_snapshot = Signal(object)      # DepthSnapshotEvent
    depth_update = Signal(object)        # DepthUpdateEvent

    tickers = Signal(object)             # TickersEvent

    status = Signal(str)                 # Estado textual (Connected, Error, etc.)

    # ------------------------------------------------------
    # INIT
    # ------------------------------------------------------

    def __init__(
        self,
        parent=None,
        initial_symbol: str = "BTCUSDT",
        initial_timeframe: str = "1m",
    ):
        super().__init__(parent)

        self._logger = logging.getLogger(__name__)

        # Estados globais
        self._symbol_state = SymbolState(initial_symbol)
        self._timeframe_state = TimeframeState(initial_timeframe)

        # Cache
        self._cache = CacheManager()

        # Provider (lazy)
        self._provider: Optional[BinanceProvider] = None

        # Controlo lifecycle
        self._lock = threading.Lock()
        self._started = False

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def start(self):
        """
        Arranca o engine e o provider.
        """
        with self._lock:
            if self._started:
                return
            self._started = True

        try:
            self._logger.info(
                "CoreDataEngine starting for %s %s",
                self._symbol_state.symbol,
                self._timeframe_state.timeframe,
            )

            # ------------------------------------------------
            # PROVIDER (NOVO MODELO)
            # ------------------------------------------------

            self._provider = BinanceProvider(engine=self)

            self._provider.start(
                self._symbol_state.symbol,
                self._timeframe_state.timeframe,
            )

            # Estado inicial para UI
            self.symbol_changed.emit(
                SymbolChanged(symbol=self._symbol_state.symbol)
            )
            self.timeframe_changed.emit(
                TimeframeChanged(timeframe=self._timeframe_state.timeframe)
            )
            self.status.emit("Connected")

            self._logger.info("CoreDataEngine started successfully")

        except Exception as e:
            self._logger.exception("Failed to start CoreDataEngine")
            self.status.emit(f"Error: {e}")
            with self._lock:
                self._started = False

    def stop(self):
        """
        Para completamente o engine.
        """
        with self._lock:
            self._started = False

        if self._provider:
            try:
                self._provider.stop()
            except Exception:
                pass
            self._provider = None

    # ======================================================
    # SYMBOL / TIMEFRAME
    # ======================================================

    def set_symbol(self, symbol: str):
        prev = self._symbol_state.symbol
        new = self._symbol_state.set(symbol)

        if new == prev:
            return

        self._logger.info("Symbol -> %s", new)
        self.symbol_changed.emit(SymbolChanged(symbol=new))

        if self._provider:
            self._provider.set_symbol_timeframe(
                new,
                self._timeframe_state.timeframe,
            )

    def set_timeframe(self, timeframe: str):
        prev = self._timeframe_state.timeframe
        new = self._timeframe_state.set(timeframe)

        if new == prev:
            return

        self._logger.info("Timeframe -> %s", new)
        self.timeframe_changed.emit(TimeframeChanged(timeframe=new))

        if self._provider:
            self._provider.set_symbol_timeframe(
                self._symbol_state.symbol,
                new,
            )

    # ======================================================
    # MÉTODOS CHAMADOS PELO PROVIDER
    # ======================================================
    # ⚠️ ESTES MÉTODOS SÃO INVOCADOS PELO BinanceProvider
    #     VIA engine.<method>()
    # ======================================================

    def on_history(self, symbol: str, timeframe: str, candles: list[Candle]):
        self._cache.set_history(symbol, timeframe, candles)

        self.candle_history.emit(
            CandleHistory(
                symbol=symbol.upper(),
                timeframe=timeframe,
                candles=candles,
            )
        )

    def on_candle_update(
        self,
        symbol: str,
        timeframe: str,
        candle: Candle,
        closed: bool,
    ):
        self._cache.append_candle(symbol, timeframe, candle, closed)

        self.candle_update.emit(
            CandleUpdate(
                symbol=symbol.upper(),
                timeframe=timeframe,
                candle=candle,
                closed=closed,
            )
        )

    def on_trade(self, symbol: str, trade: Trade):
        self._cache.append_trade(symbol, trade)
        self.trade.emit(TradeEvent(trade=trade))

    def on_depth_snapshot(self, evt: DepthSnapshotEvent):
        self._cache.set_depth(
            evt.symbol,
            evt.bids,
            evt.asks,
            evt.last_update_id,
        )
        self.depth_snapshot.emit(evt)

    def on_depth_update(self, evt: DepthUpdateEvent):
        self._cache.set_depth(
            evt.symbol,
            evt.bids,
            evt.asks,
            evt.last_update_id,
        )
        self.depth_update.emit(evt)

    def on_tickers(self, payload):
        self.tickers.emit(TickersEvent(tickers=payload))

    def on_status(self, status: str):
        self.status.emit(status)
