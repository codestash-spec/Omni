# ==========================================================
# BINANCE PROVIDER
# ==========================================================
# Responsável por:
# - Fetch inicial de histórico (REST)
# - Streams em tempo real (WebSocket)
# - Emitir eventos para o CoreDataEngine
#
# Este provider é desenhado para:
# - correr num thread dedicado
# - usar asyncio internamente
# - nunca bloquear a UI
# ==========================================================

import asyncio
import json
import logging
import threading
from typing import Optional

import aiohttp
import websockets

# ==========================================================
# MODELOS + EVENTOS
# ==========================================================

from core.data_engine.models import Candle, Trade
from core.data_engine.events import (
    CandleHistory,
    CandleUpdate,
    TradeEvent,
)

# ==========================================================
# BINANCE PROVIDER
# ==========================================================

class BinanceProvider:
    """
    Provider de dados Binance (Spot).

    Pipeline:
    1️⃣ REST → histórico inicial (candles)
    2️⃣ WS   → trades + candles em tempo real
    """

    def __init__(self, engine):
        self.engine = engine
        self._logger = logging.getLogger(__name__)

        # Thread dedicada
        self._thread: Optional[threading.Thread] = None

        # Event loop asyncio (privado)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Sessão HTTP
        self._session: Optional[aiohttp.ClientSession] = None

        # Estado
        self._running = False
        self._symbol = None
        self._timeframe = None

    # ======================================================
    # START / STOP
    # ======================================================

    def start(self, symbol: str, timeframe: str):
        """
        Arranca o provider num thread separado.
        """
        if self._running:
            return

        self._symbol = symbol
        self._timeframe = timeframe
        self._running = True

        self._thread = threading.Thread(
            target=self._run,
            name="BinanceUnified",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        """
        Para o provider de forma segura.
        """
        self._running = False

        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)

    # ======================================================
    # THREAD ENTRYPOINT
    # ======================================================

    def _run(self):
        """
        Entry point do thread.
        Cria um event loop próprio.
        """
        try:
            asyncio.run(self._main(self._symbol, self._timeframe))
        except Exception as e:
            self._logger.exception("BinanceProvider crashed: %s", e)

    # ======================================================
    # MAIN ASYNC
    # ======================================================

    async def _main(self, symbol: str, timeframe: str):
        """
        Função principal async.
        """
        self._loop = asyncio.get_running_loop()

        async with aiohttp.ClientSession() as session:
            self._session = session

            # 1️⃣ PREFETCH (HISTÓRICO)
            await self._prefetch(symbol, timeframe)

            # 2️⃣ STREAMS EM PARALELO
            tasks = [
                asyncio.create_task(self._trade_stream(symbol)),
                asyncio.create_task(self._kline_stream(symbol, timeframe)),
            ]

            self._logger.info("Binance streams started for %s %s", symbol, timeframe)

            while self._running:
                await asyncio.sleep(0.25)

            # Cleanup
            for t in tasks:
                t.cancel()

    # ======================================================
    # PREFETCH (HISTÓRICO)
    # ======================================================

    async def _prefetch(self, symbol: str, timeframe: str):
        """
        Fetch inicial de candles (REST).
        """
        history = await self._fetch_history(symbol, timeframe, limit=900)

        # Emite evento para o Core
        self.engine.candle_history.emit(
            CandleHistory(
                symbol=symbol,
                timeframe=timeframe,
                candles=history,
            )
        )

    async def _fetch_history(self, symbol: str, timeframe: str, limit: int = 500):
        """
        REST call ao endpoint /klines da Binance.
        """

        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
        }

        interval = interval_map.get(timeframe)
        if not interval:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }

        async with self._session.get(url, params=params) as resp:
            data = await resp.json()

        candles = []
        for k in data:
            candles.append(
                Candle(
                    open_time=int(k[0]),
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                )
            )

        self._logger.info(
            "Fetched %d candles for %s %s",
            len(candles),
            symbol,
            timeframe,
        )

        return candles

    # ======================================================
    # STREAM: TRADES
    # ======================================================

    async def _trade_stream(self, symbol: str):
        """
        Stream de trades em tempo real.
        """
        url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@trade"

        async with websockets.connect(url) as ws:
            async for msg in ws:
                if not self._running:
                    break

                data = json.loads(msg)

                trade = Trade(
                    symbol=symbol,
                    price=float(data["p"]),
                    qty=float(data["q"]),
                    side="Buy" if not data["m"] else "Sell",
                    ts=int(data["T"]),
                )

                self.engine.trade.emit(
                    TradeEvent(trade=trade)
                )

    # ======================================================
    # STREAM: CANDLES (KLINES)
    # ======================================================

    async def _kline_stream(self, symbol: str, timeframe: str):
        """
        Stream de candles em tempo real.
        """
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
        }

        interval = interval_map[timeframe]
        url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@kline_{interval}"

        async with websockets.connect(url) as ws:
            async for msg in ws:
                if not self._running:
                    break

                data = json.loads(msg)
                k = data["k"]

                candle = Candle(
                    open_time=int(k["t"]),
                    open=float(k["o"]),
                    high=float(k["h"]),
                    low=float(k["l"]),
                    close=float(k["c"]),
                    volume=float(k["v"]),
                )

                self.engine.candle_update.emit(
                    CandleUpdate(
                        symbol=symbol,
                        timeframe=timeframe,
                        candle=candle,
                        closed=k["x"],
                    )
                )
