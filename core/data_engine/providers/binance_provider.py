import asyncio
import contextlib
import json
import logging
import threading
import time
from typing import Awaitable, Callable, Dict, List, Tuple

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed

from data_engine.models import TickerData, Candle, Trade
from core.data_engine.events import DepthSnapshotEvent, DepthUpdateEvent


HistoryCallback = Callable[[str, str, List[Candle]], None]
CandleCallback = Callable[[str, str, Candle, bool], None]
TradeCallback = Callable[[str, Trade], None]
DepthSnapshotCallback = Callable[[DepthSnapshotEvent], None]
DepthUpdateCallback = Callable[[DepthUpdateEvent], None]
TickerCallback = Callable[[List[TickerData]], None]
StatusCallback = Callable[[str], None]


class BinanceProvider:
    STREAM_URL = "wss://stream.binance.com:9443/ws"
    TICKER_URL = "wss://stream.binance.com:9443/ws/!ticker@arr"
    REST_BASE = "https://api.binance.com/api/v3"

    WATCHLIST = [
        "BTCUSDT",
        "ETHUSDT",
        "USDTUSDC",
        "XRPUSDT",
        "BNBUSDT",
        "USDCUSDT",
        "SOLUSDT",
        "TRXUSDT",
        "DOGEUSDT",
        "ADAUSDT",
    ]

    def __init__(
        self,
        on_history: HistoryCallback,
        on_candle: CandleCallback,
        on_trade: TradeCallback,
        on_depth_snapshot: DepthSnapshotCallback,
        on_depth_update: DepthUpdateCallback,
        on_tickers: TickerCallback,
        on_status: StatusCallback,
    ):
        self._on_history = on_history
        self._on_candle = on_candle
        self._on_trade = on_trade
        self._on_depth_snapshot = on_depth_snapshot
        self._on_depth_update = on_depth_update
        self._on_tickers = on_tickers
        self._on_status = on_status
        self._logger = logging.getLogger(__name__)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._symbol_tf_queue: asyncio.Queue | None = None
        self._http: aiohttp.ClientSession | None = None
        self._last_depth_update_id: int = 0
        self._depth_bids: Dict[float, float] = {}
        self._depth_asks: Dict[float, float] = {}
        self._last_ticker_emit = 0.0
        self._active_symbol = ""

    def start(self, symbol: str, timeframe: str):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, args=(symbol, timeframe), name="BinanceUnified", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2)

    def set_symbol_timeframe(self, symbol: str, timeframe: str):
        if self._loop and self._symbol_tf_queue:
            asyncio.run_coroutine_threadsafe(self._symbol_tf_queue.put((symbol.lower(), timeframe)), self._loop)
            self._logger.info("Queued symbol/timeframe switch -> %s %s", symbol.upper(), timeframe)

    def _run(self, symbol: str, timeframe: str):
        asyncio.run(self._main(symbol, timeframe))

    async def _main(self, symbol: str, timeframe: str):
        self._loop = asyncio.get_running_loop()
        self._symbol_tf_queue = asyncio.Queue()
        await self._symbol_tf_queue.put((symbol.lower(), timeframe))
        async with aiohttp.ClientSession() as session:
            self._http = session
            ticker_task = asyncio.create_task(self._ticker_loop())
            router_task = asyncio.create_task(self._symbol_router())
            try:
                await asyncio.gather(ticker_task, router_task)
            except asyncio.CancelledError:
                pass
            finally:
                for t in (ticker_task, router_task):
                    t.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await t

    async def _ticker_loop(self):
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(self.TICKER_URL, ping_interval=20) as ws:
                    self._on_status("connected")
                    async for msg in ws:
                        if self._stop_event.is_set():
                            break
                        data = json.loads(msg)
                        tickers = self._parse_ticker_arr(data)
                        now = time.perf_counter()
                        if tickers and now - self._last_ticker_emit >= 0.4:
                            self._on_tickers(tickers)
                            self._last_ticker_emit = now
            except (ConnectionClosed, OSError, asyncio.TimeoutError):
                self._on_status("reconnecting")
                await asyncio.sleep(1)
            except Exception:
                self._logger.exception("Ticker stream error")
                await asyncio.sleep(1)
        self._on_status("disconnected")

    async def _symbol_router(self):
        current_symbol = None
        current_timeframe = None
        trade_task = None
        candle_task = None
        depth_task = None
        while not self._stop_event.is_set():
            symbol, timeframe = await self._symbol_tf_queue.get()
            drained = 0
            while not self._symbol_tf_queue.empty():
                symbol, timeframe = await self._symbol_tf_queue.get()
                drained += 1
            if symbol == current_symbol and timeframe == current_timeframe:
                continue
            if drained:
                self._logger.info("Symbol queue drained %d pending requests; using %s %s", drained, symbol.upper(), timeframe)
            current_symbol, current_timeframe = symbol, timeframe
            self._active_symbol = symbol
            for task in (trade_task, candle_task, depth_task):
                if task:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            await self._prefetch(current_symbol, current_timeframe)
            trade_task = asyncio.create_task(self._trade_loop(current_symbol))
            candle_task = asyncio.create_task(self._kline_loop(current_symbol, current_timeframe))
            depth_task = asyncio.create_task(self._depth_loop(current_symbol))

    async def _prefetch(self, symbol: str, timeframe: str):
        if not self._http:
            return
        history = await self._fetch_history(symbol, timeframe, limit=900)
        if history:
            self._on_history(symbol.upper(), timeframe, history)
        snapshot, last_id = await self._fetch_depth_snapshot(symbol)
        if snapshot:
            self._last_depth_update_id = last_id
            self._depth_bids = {float(p): float(q) for p, q in snapshot["bids"] if float(q) > 0}
            self._depth_asks = {float(p): float(q) for p, q in snapshot["asks"] if float(q) > 0}
            bids_list = sorted([(p, q) for p, q in self._depth_bids.items()], key=lambda x: x[0], reverse=True)
            asks_list = sorted([(p, q) for p, q in self._depth_asks.items()], key=lambda x: x[0])
            self._on_depth_snapshot(
                DepthSnapshotEvent(symbol=symbol.upper(), bids=bids_list, asks=asks_list, last_update_id=last_id)
            )

    async def _trade_loop(self, symbol: str):
        url = f"{self.STREAM_URL}/{symbol}@trade"
        last_trade_ts = 0.0
        connected_at = 0.0
        while not self._stop_event.is_set():
            try:
                self._logger.info("Trade stream connecting -> %s", symbol.upper())
                async with websockets.connect(url, ping_interval=20) as ws:
                    self._logger.info("Trade stream connected -> %s", symbol.upper())
                    connected_at = time.perf_counter()
                    async for msg in ws:
                        if self._stop_event.is_set():
                            break
                        data = json.loads(msg)
                        trade = self._parse_trade(data)
                        if trade:
                            last_trade_ts = time.perf_counter()
                            self._on_trade(symbol.upper(), trade)
                        else:
                            now = time.perf_counter()
                            if last_trade_ts and now - last_trade_ts > 60:
                                self._logger.warning("Trade stream idle >60s for %s (no valid trades parsed)", symbol.upper())
                            elif not last_trade_ts and connected_at and now - connected_at > 30:
                                self._logger.warning("Trade stream connected but no trades for 30s -> %s", symbol.upper())
                    self._logger.warning("Trade stream ended unexpectedly -> %s", symbol.upper())
            except (ConnectionClosed, OSError, asyncio.TimeoutError):
                self._logger.warning("Trade stream reconnecting after socket issue -> %s", symbol.upper())
                await asyncio.sleep(1)
            except Exception:
                self._logger.exception("Trade stream error")
                await asyncio.sleep(1)

    async def _kline_loop(self, symbol: str, timeframe: str):
        url = f"{self.STREAM_URL}/{symbol}@kline_{timeframe}"
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    async for msg in ws:
                        if self._stop_event.is_set():
                            break
                        data = json.loads(msg)
                        update = self._parse_kline(data, timeframe)
                        if update:
                            self._on_candle(symbol.upper(), timeframe, update[0], update[1])
            except (ConnectionClosed, OSError, asyncio.TimeoutError):
                await asyncio.sleep(1)
            except Exception:
                self._logger.exception("Kline stream error")
                await asyncio.sleep(1)

    async def _depth_loop(self, symbol: str):
        # Binance diff depth stream
        url = f"{self.STREAM_URL}/{symbol}@depth20@100ms"
        throttle_at = time.perf_counter()
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    async for msg in ws:
                        if self._stop_event.is_set():
                            break
                        data = json.loads(msg)
                        bids, asks, update_id = self._apply_depth_diff(data, symbol)
                        now = time.perf_counter()
                        if bids is not None and asks is not None and now - throttle_at >= 0.1:
                            self._on_depth_update(
                                DepthUpdateEvent(
                                    symbol=symbol.upper(),
                                    bids=bids,
                                    asks=asks,
                                    last_update_id=update_id,
                                )
                            )
                            throttle_at = now
            except (ConnectionClosed, OSError, asyncio.TimeoutError):
                await asyncio.sleep(1)
            except Exception:
                self._logger.exception("Depth stream error")
                await asyncio.sleep(1)

    async def _fetch_history(self, symbol: str, timeframe: str, limit: int = 900) -> List[Candle]:
        if not self._http:
            return []
        params = {"symbol": symbol.upper(), "interval": timeframe, "limit": limit}
        url = f"{self.REST_BASE}/klines"
        try:
            async with self._http.get(url, params=params, timeout=10) as resp:
                resp.raise_for_status()
                raw = await resp.json()
        except Exception:
            self._logger.exception("History fetch failed for %s %s", symbol.upper(), timeframe)
            return []
        candles: List[Candle] = []
        for entry in raw:
            try:
                candles.append(
                    Candle(
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

    async def _fetch_depth_snapshot(self, symbol: str, limit: int = 50):
        if not self._http:
            return None, 0
        params = {"symbol": symbol.upper(), "limit": limit}
        url = f"{self.REST_BASE}/depth"
        try:
            async with self._http.get(url, params=params, timeout=10) as resp:
                resp.raise_for_status()
                raw = await resp.json()
                return raw, int(raw.get("lastUpdateId", 0))
        except Exception:
            self._logger.exception("Depth snapshot fetch failed for %s", symbol.upper())
            return None, 0

    def _parse_ticker_arr(self, payload) -> List[TickerData]:
        results = []
        for item in payload:
            sym = item.get("s")
            if sym not in self.WATCHLIST:
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
                    symbol=sym,
                    last_price=last_price,
                    pct_change=pct_change,
                    volume=volume,
                    bid=bid,
                    ask=ask,
                )
            )
        return results

    def _parse_trade(self, payload) -> Trade | None:
        try:
            price = float(payload.get("p", 0))
            qty = float(payload.get("q", 0))
            ts = int(payload.get("T", 0))
            side = "Sell" if payload.get("m", False) else "Buy"
            symbol = payload.get("s", "").upper()
            return Trade(symbol=symbol, price=price, qty=qty, side=side, ts=ts)
        except (TypeError, ValueError):
            return None

    def _parse_kline(self, payload, timeframe: str):
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
            return candle, closed
        except (TypeError, ValueError):
            return None

    def _apply_depth_diff(self, payload, symbol: str):
        if not payload:
            return None, None, None
        first_id = payload.get("U")
        last_id = payload.get("u")
        if not first_id or not last_id:
            return None, None, None
        if self._last_depth_update_id and last_id <= self._last_depth_update_id:
            return None, None, None
        if self._last_depth_update_id and first_id > self._last_depth_update_id + 1000:
            # lost sync, need new snapshot
            self._logger.warning("Depth diff gap detected; requesting new snapshot")
            asyncio.create_task(self._resync_depth(symbol))  # fire and forget
            return None, None, None

        bids = payload.get("b", [])
        asks = payload.get("a", [])
        for price_str, qty_str in bids:
            price = float(price_str)
            qty = float(qty_str)
            if qty == 0:
                self._depth_bids.pop(price, None)
            else:
                self._depth_bids[price] = qty
        for price_str, qty_str in asks:
            price = float(price_str)
            qty = float(qty_str)
            if qty == 0:
                self._depth_asks.pop(price, None)
            else:
                self._depth_asks[price] = qty
        self._last_depth_update_id = last_id
        bids_list = sorted([(p, q) for p, q in self._depth_bids.items()], key=lambda x: x[0], reverse=True)[:50]
        asks_list = sorted([(p, q) for p, q in self._depth_asks.items()], key=lambda x: x[0])[:50]
        return bids_list, asks_list, last_id

    async def _resync_depth(self, symbol: str):
        snapshot, last_id = await self._fetch_depth_snapshot(symbol=symbol)
        if not snapshot:
            return
        self._depth_bids = {float(p): float(q) for p, q in snapshot["bids"] if float(q) > 0}
        self._depth_asks = {float(p): float(q) for p, q in snapshot["asks"] if float(q) > 0}
        self._last_depth_update_id = last_id
        bids_list = sorted([(p, q) for p, q in self._depth_bids.items()], key=lambda x: x[0], reverse=True)
        asks_list = sorted([(p, q) for p, q in self._depth_asks.items()], key=lambda x: x[0])
        self._on_depth_snapshot(
            DepthSnapshotEvent(symbol=symbol.upper(), bids=bids_list, asks=asks_list, last_update_id=last_id)
        )
