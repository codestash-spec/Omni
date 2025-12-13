import asyncio
import json
import logging
import threading
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from data_engine.events import CandleUpdated, TradeReceived
from data_engine.models import Candle, Trade


class RealtimeStream:
    STREAM_URL = "wss://stream.binance.com:9443/ws"

    def __init__(
        self,
        on_candle: Callable[[CandleUpdated], None],
        on_trade: Callable[[TradeReceived], None],
    ):
        self._on_candle = on_candle
        self._on_trade = on_trade
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._logger = logging.getLogger(__name__)
        self._symbol = "BTCUSDT"
        self._timeframe = "1m"

    def start(self, symbol: str, timeframe: str):
        self.stop()
        self._symbol = symbol.lower()
        self._timeframe = timeframe
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="RealtimeStream", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self):
        asyncio.run(self._main())

    async def _main(self):
        tasks = [
            asyncio.create_task(self._trade_loop()),
            asyncio.create_task(self._kline_loop()),
        ]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            for t in tasks:
                t.cancel()

    async def _trade_loop(self):
        url = f"{self.STREAM_URL}/{self._symbol}@trade"
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    async for msg in ws:
                        if self._stop_event.is_set():
                            break
                        data = json.loads(msg)
                        trade = self._parse_trade(data)
                        if trade:
                            self._on_trade(TradeReceived(trade=trade))
            except (ConnectionClosed, OSError, asyncio.TimeoutError):
                await asyncio.sleep(1)
            except Exception:
                self._logger.exception("Trade stream error; retrying")
                await asyncio.sleep(1)

    async def _kline_loop(self):
        url = f"{self.STREAM_URL}/{self._symbol}@kline_{self._timeframe}"
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    async for msg in ws:
                        if self._stop_event.is_set():
                            break
                        data = json.loads(msg)
                        event = self._parse_kline(data)
                        if event:
                            self._on_candle(event)
            except (ConnectionClosed, OSError, asyncio.TimeoutError):
                await asyncio.sleep(1)
            except Exception:
                self._logger.exception("Kline stream error; retrying")
                await asyncio.sleep(1)

    def _parse_trade(self, payload) -> Optional[Trade]:
        try:
            price = float(payload.get("p", 0))
            qty = float(payload.get("q", 0))
            ts = int(payload.get("T", 0))
            side = "Sell" if payload.get("m", False) else "Buy"
            symbol = payload.get("s", "").upper()
            return Trade(symbol=symbol, price=price, qty=qty, side=side, ts=ts)
        except (TypeError, ValueError):
            return None

    def _parse_kline(self, payload) -> Optional[CandleUpdated]:
        kline = payload.get("k")
        if not kline:
            return None
        try:
            candle = Candle(
                open_time=int(kline.get("t")),
                open=float(kline.get("o")),
                high=float(kline.get("h")),
                low=float(kline.get("l")),
                close=float(kline.get("c")),
                volume=float(kline.get("v")),
            )
            closed = bool(kline.get("x", False))
            symbol = kline.get("s", "").upper()
            return CandleUpdated(symbol=symbol, timeframe=self._timeframe, candle=candle, closed=closed)
        except (TypeError, ValueError):
            return None
