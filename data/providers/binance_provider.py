import asyncio
import contextlib
import json
import logging
import threading
import time
from typing import Dict, List

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed

from core.app_state import AppState
from core.models import CandleData, TickerData, TradeData
from data.event_bus import EventBus


class BinanceProvider:
    """
    Read-only public market data provider for Binance.
    Streams:
      - !ticker@arr (filtered to watchlist) -> market tickers
      - <symbol>@trade -> trades for active symbol
      - <symbol>@kline_1m -> 1m candles for active symbol
    """

    STREAM_URL = "wss://stream.binance.com:9443/ws"
    TICKER_URL = "wss://stream.binance.com:9443/ws/!ticker@arr"
    WATCHLIST = [
        "BTCUSDT",
        "ETHUSDT",
        "USDTUSDC",  # stable pair to represent USDT
        "XRPUSDT",
        "BNBUSDT",
        "USDCUSDT",
        "SOLUSDT",
        "TRXUSDT",
        "DOGEUSDT",
        "ADAUSDT",
    ]

    def __init__(self, bus: EventBus, app_state: AppState):
        self.bus = bus
        self.app_state = app_state
        self._logger = logging.getLogger(__name__)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._symbol_queue: asyncio.Queue | None = None
        self._stop_event = threading.Event()
        self._candle_cache: Dict[int, CandleData] = {}
        self._http_session: aiohttp.ClientSession | None = None
        self._last_ticker_emit = 0.0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="BinanceProvider", daemon=True)
        self._thread.start()
        self._logger.debug("BinanceProvider thread started")

    def stop(self):
        self._stop_event.set()
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2)
        self._logger.debug("BinanceProvider thread stopped")

    def set_symbol(self, symbol: str):
        symbol = symbol.lower()
        if self._loop and self._symbol_queue:
            asyncio.run_coroutine_threadsafe(self._symbol_queue.put(symbol), self._loop)
        self._logger.info("Provider queued symbol change -> %s", symbol)

    def _run(self):
        asyncio.run(self._main())

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        self._symbol_queue = asyncio.Queue()
        await self._symbol_queue.put(self.app_state.current_symbol.lower())
        self.app_state.set_status("connecting")

        tasks = []
        try:
            async with aiohttp.ClientSession() as session:
                self._http_session = session
                tasks = [
                    asyncio.create_task(self._ticker_loop()),
                    asyncio.create_task(self._symbol_router()),
                ]
                await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        try:
            for t in tasks:
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await t
        finally:
            self.app_state.set_status("disconnected")
            self._logger.info("Provider main loop exited")

    async def _ticker_loop(self):
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(self.TICKER_URL, ping_interval=20) as ws:
                    self.app_state.set_status("connected")
                    self._logger.info("Ticker stream connected")
                    last_log = time.perf_counter()
                    async for msg in ws:
                        if self._stop_event.is_set():
                            break
                        data = json.loads(msg)
                        tickers = self._parse_ticker_arr(data)
                        if tickers:
                            now = time.perf_counter()
                            # throttle to avoid UI flooding
                            if now - self._last_ticker_emit >= 0.5:
                                self.bus.publish_tickers(tickers)
                                self._last_ticker_emit = now
                            now = time.perf_counter()
                            if now - last_log >= 5:
                                sample = tickers[0]
                                self._logger.info(
                                    "Tickers update: %d symbols; sample %s last=%.4f pct=%.2f vol=%.0f",
                                    len(tickers),
                                    sample.symbol,
                                    sample.last_price,
                                    sample.pct_change,
                                    sample.volume,
                                )
                                last_log = now
            except (ConnectionClosed, OSError, asyncio.TimeoutError):
                self._logger.warning("Ticker stream disconnected, retrying...")
                await asyncio.sleep(1)
            except Exception:
                self._logger.exception("Ticker stream error; retrying")
                await asyncio.sleep(1)

    async def _symbol_router(self):
        current_symbol = None
        trade_task = None
        candle_task = None
        while not self._stop_event.is_set():
            symbol = await self._symbol_queue.get()
            # Drain fast-click bursts and keep only the last requested symbol.
            drained = 0
            while not self._symbol_queue.empty():
                symbol = await self._symbol_queue.get()
                drained += 1
            if symbol == current_symbol:
                continue
            if drained:
                self._logger.info("Symbol queue drained %d pending requests, keeping last=%s", drained, symbol.upper())
            current_symbol = symbol
            self._candle_cache.clear()
            # prefill with history before live stream
            self._logger.info("Switching streams to %s", current_symbol.upper())
            start_hist = time.perf_counter()
            history = await self._fetch_history(current_symbol)
            if history:
                for c in history:
                    self._candle_cache[c.open_time] = c
                candles = [self._candle_cache[k] for k in sorted(self._candle_cache.keys())][-500:]
                self.bus.publish_candles(candles)
                self._logger.info(
                    "History loaded for %s (%d candles) in %.3fs",
                    current_symbol.upper(),
                    len(candles),
                    time.perf_counter() - start_hist,
                )
            if trade_task:
                trade_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await trade_task
            if candle_task:
                candle_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await candle_task
            trade_task = asyncio.create_task(self._trade_loop(current_symbol))
            candle_task = asyncio.create_task(self._kline_loop(current_symbol))

    async def _trade_loop(self, symbol: str):
        url = f"{self.STREAM_URL}/{symbol}@trade"
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    self._logger.info("Trade stream connected for %s", symbol.upper())
                    count = 0
                    start = time.perf_counter()
                    async for msg in ws:
                        if self._stop_event.is_set():
                            break
                        data = json.loads(msg)
                        trade = self._parse_trade(data)
                        if trade:
                            self.bus.publish_trade(trade)
                            count += 1
                            if count % 25 == 0:
                                elapsed = time.perf_counter() - start
                                self._logger.debug(
                                    "Trade stream %s processed %d trades in %.2fs (last %.2f @ %.4f)",
                                    symbol.upper(),
                                    count,
                                    elapsed,
                                    trade.qty,
                                    trade.price,
                                )
            except (ConnectionClosed, OSError, asyncio.TimeoutError):
                self._logger.warning("Trade stream dropped for %s, retrying...", symbol.upper())
                await asyncio.sleep(1)
            except Exception:
                self._logger.exception("Trade stream error for %s; retrying", symbol.upper())
                await asyncio.sleep(1)

    async def _kline_loop(self, symbol: str):
        url = f"{self.STREAM_URL}/{symbol}@kline_1m"
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    self._logger.info("Kline stream connected for %s", symbol.upper())
                    count = 0
                    start = time.perf_counter()
                    async for msg in ws:
                        if self._stop_event.is_set():
                            break
                        data = json.loads(msg)
                        candle = self._parse_kline(data)
                        if candle:
                            self._candle_cache[candle.open_time] = candle
                            candles = [self._candle_cache[k] for k in sorted(self._candle_cache.keys())][-300:]
                            self.bus.publish_candles(candles)
                            count += 1
                            if count % 50 == 0:
                                elapsed = time.perf_counter() - start
                                self._logger.info(
                                    "Kline stream %s processed %d updates in %.2fs",
                                    symbol.upper(),
                                    count,
                                    elapsed,
                                )
            except (ConnectionClosed, OSError, asyncio.TimeoutError):
                self._logger.warning("Kline stream dropped for %s, retrying...", symbol.upper())
                await asyncio.sleep(1)
            except Exception:
                self._logger.exception("Kline stream error for %s; retrying", symbol.upper())
                await asyncio.sleep(1)

    def _parse_ticker_arr(self, payload) -> List[TickerData]:
        results = []
        for item in payload:
            symbol = item.get("s")
            if symbol not in self.WATCHLIST:
                continue
            try:
                last_price = float(item.get("c", 0))
                pct_change = float(item.get("P", 0))
                volume = float(item.get("v", 0))
                bid = float(item.get("b", 0))
                ask = float(item.get("a", 0))
            except (TypeError, ValueError):
                continue
            results.append(
                TickerData(
                    symbol=symbol,
                    last_price=last_price,
                    pct_change=pct_change,
                    volume=volume,
                    bid=bid,
                    ask=ask,
                )
            )
        return results

    def _parse_trade(self, payload) -> TradeData | None:
        try:
            price = float(payload.get("p", 0))
            qty = float(payload.get("q", 0))
            ts = int(payload.get("T", 0))
            is_sell = payload.get("m", False)
            side = "Sell" if is_sell else "Buy"
            symbol = payload.get("s", "").upper()
            return TradeData(symbol=symbol, price=price, qty=qty, side=side, ts=ts)
        except (TypeError, ValueError):
            return None

    def _parse_kline(self, payload) -> CandleData | None:
        kline = payload.get("k")
        if not kline:
            return None
        try:
            open_time = int(kline.get("t"))
            open_p = float(kline.get("o"))
            high = float(kline.get("h"))
            low = float(kline.get("l"))
            close = float(kline.get("c"))
            vol = float(kline.get("v"))
            symbol = kline.get("s", "").upper()
            return CandleData(
                symbol=symbol,
                open_time=open_time,
                open=open_p,
                high=high,
                low=low,
                close=close,
                volume=vol,
            )
        except (TypeError, ValueError):
            return None

    async def _fetch_history(self, symbol: str) -> List[CandleData]:
        if not self._http_session:
            return []
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval=1m&limit=500"
        try:
            async with self._http_session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError):
            self._logger.exception("History fetch failed for %s", symbol.upper())
            return []
        candles: List[CandleData] = []
        for entry in data:
            try:
                candles.append(
                    CandleData(
                        symbol=symbol.upper(),
                        open_time=int(entry[0]),
                        open=float(entry[1]),
                        high=float(entry[2]),
                        low=float(entry[3]),
                        close=float(entry[4]),
                        volume=float(entry[5]),
                    )
                )
            except (TypeError, ValueError, IndexError):
                continue
        return candles
