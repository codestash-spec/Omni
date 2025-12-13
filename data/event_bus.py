from PySide6.QtCore import QObject, Signal

from core.app_state import AppState


class EventBus(QObject):
    market_tickers = Signal(list)  # List[TickerData]
    trade = Signal(object)  # TradeData
    candles = Signal(list)  # List[CandleData]
    status = Signal(str)
    symbol_changed = Signal(str)

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.app_state.symbol_changed.connect(self.symbol_changed.emit)
        self.app_state.status_changed.connect(self.status.emit)

    def publish_tickers(self, data):
        self.market_tickers.emit(data)

    def publish_trade(self, trade):
        self.trade.emit(trade)

    def publish_candles(self, candles):
        self.candles.emit(candles)

    def publish_status(self, status: str):
        self.status.emit(status)
