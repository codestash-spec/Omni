import threading


class SymbolState:
    def __init__(self, initial_symbol: str = "BTCUSDT"):
        self._lock = threading.Lock()
        self._symbol = initial_symbol.upper()

    @property
    def symbol(self) -> str:
        with self._lock:
            return self._symbol

    def set(self, symbol: str) -> str:
        symbol = symbol.upper()
        with self._lock:
            if symbol == self._symbol:
                return self._symbol
            self._symbol = symbol
            return self._symbol

