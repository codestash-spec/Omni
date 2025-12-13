import threading


class TimeframeState:
    def __init__(self, initial_timeframe: str = "1m"):
        self._lock = threading.Lock()
        self._timeframe = initial_timeframe

    @property
    def timeframe(self) -> str:
        with self._lock:
            return self._timeframe

    def set(self, timeframe: str) -> str:
        tf = timeframe.lower()
        with self._lock:
            if tf == self._timeframe:
                return self._timeframe
            self._timeframe = tf
            return self._timeframe

