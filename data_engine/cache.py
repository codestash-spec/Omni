from typing import Dict, Tuple, Any


class DataCache:
    def __init__(self):
        self._mem: Dict[Tuple[str, str], Any] = {}

    def get(self, symbol: str, timeframe: str):
        return self._mem.get((symbol.upper(), timeframe))

    def set(self, symbol: str, timeframe: str, data) -> None:
        self._mem[(symbol.upper(), timeframe)] = data

    # Placeholder for future disk persistence
    def clear(self):
        self._mem.clear()
