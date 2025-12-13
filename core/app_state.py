from PySide6.QtCore import QObject, Signal


class AppState(QObject):
    symbol_changed = Signal(str)
    status_changed = Signal(str)

    def __init__(self, initial_symbol: str = "BTCUSDT", asset_class: str = "Crypto"):
        super().__init__()
        self.current_symbol = initial_symbol.upper()
        self.asset_class = asset_class
        self.connection_status = "disconnected"

    def set_symbol(self, symbol: str):
        symbol = symbol.upper()
        if symbol != self.current_symbol:
            self.current_symbol = symbol
            self.symbol_changed.emit(symbol)

    def set_status(self, status: str):
        if status != self.connection_status:
            self.connection_status = status
            self.status_changed.emit(status)
