import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import aiohttp

from data_engine.models import Candle


class HistoricalDataLoader:
    """
    Lightweight Binance REST loader.
    Fetches historical klines in batches to avoid re-fetch loops and guarantees enough bars for the chart.
    """

    BASE_URL = "https://api.binance.com/api/v3/klines"
    MAX_PER_REQUEST = 1000  # Binance hard limit is 1500; stay conservative

    def __init__(self):
        self._logger = logging.getLogger(__name__)

    @staticmethod
    def _timeframe_ms(timeframe: str) -> int:
        mapping = {
            "1m": 60_000,
            "3m": 180_000,
            "5m": 300_000,
            "15m": 900_000,
            "30m": 1_800_000,
            "1h": 3_600_000,
            "2h": 7_200_000,
            "4h": 14_400_000,
            "6h": 21_600_000,
            "8h": 28_800_000,
            "12h": 43_200_000,
            "1d": 86_400_000,
        }
        return mapping.get(timeframe.lower(), 60_000)

    async def _fetch(
        self,
        session: aiohttp.ClientSession,
        symbol: str,
        timeframe: str,
        limit: int,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ):
        params = {"symbol": symbol.upper(), "interval": timeframe, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        async with session.get(self.BASE_URL, params=params, timeout=15) as resp:
            resp.raise_for_status()
            return await resp.json()

    def load_ohlc(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 300,
        lookback_days: int = 365,
        max_candles: int = 5000,
    ) -> List[Candle]:
        """
        Fetch batched klines up to max_candles or lookback_days (whichever comes first).
        """

        async def _run():
            candles: List[Candle] = []
            interval_ms = self._timeframe_ms(timeframe)
            if interval_ms <= 0:
                return candles

            batch_limit = min(limit, self.MAX_PER_REQUEST)
            start_ts = int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp() * 1000)
            now_ms = int(datetime.utcnow().timestamp() * 1000)

            async with aiohttp.ClientSession() as session:
                while len(candles) < max_candles and start_ts < now_ms:
                    end_ts = start_ts + batch_limit * interval_ms
                    try:
                        raw = await self._fetch(session, symbol, timeframe, batch_limit, start_ts, end_ts)
                    except Exception:
                        self._logger.exception("REST fetch failed for %s %s", symbol, timeframe)
                        break
                    if not raw:
                        break
                    parsed: List[Candle] = []
                    for entry in raw:
                        try:
                            parsed.append(
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
                    candles.extend(parsed)
                    start_ts = raw[-1][0] + interval_ms
                    if len(parsed) < batch_limit:
                        # No more data available in range
                        break

            return candles[-max_candles:]

        return asyncio.run(_run())
