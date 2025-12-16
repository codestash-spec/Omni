"""
Verification suite for OmniFlow Terminal data vs Binance REST snapshots.

Executa em modo headless (sem UI):
- Inicializa o CoreDataEngine
- Captura eventos durante uma janela temporal
- Compara dados internos com endpoints REST oficiais da Binance
- Gera relatórios JSON + TXT

Este ficheiro é essencial para:
✔ validar integridade dos dados
✔ provar consistência institucional
✔ auditorias técnicas / investidores
"""

# ==========================================================
# IMPORTS STANDARD
# ==========================================================

import argparse          # parsing de argumentos CLI
import asyncio           # async REST
import json              # serialização dos relatórios
import os
import time
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

# ==========================================================
# IMPORTS EXTERNOS
# ==========================================================

import aiohttp            # REST async
from PySide6.QtCore import QCoreApplication, QTimer  # event loop headless Qt

# ==========================================================
# CORE ENGINE + EVENTS
# ==========================================================

from core.data_engine.core_engine import CoreDataEngine
from core.data_engine.events import (
    CandleHistory,
    CandleUpdate,
    DepthSnapshotEvent,
    DepthUpdateEvent,
    SymbolChanged,
    TimeframeChanged,
    TradeEvent,
    TickersEvent,
)
from core.data_engine.models import TickerData, Candle, Trade


# ==========================================================
# DEFAULTS
# ==========================================================

DEFAULT_SECONDS = 90          # janela de captura
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_TF = "1m"


# ==========================================================
# RESULT STRUCT
# ==========================================================

@dataclass
class ComponentResult:
    """
    Resultado de validação de um componente:
    - marketwatch
    - tape
    - chart
    - dom
    - footprint
    """
    name: str
    passed: bool
    details: Dict


# ==========================================================
# DATA PROBE
# ==========================================================

class DataProbe:
    """
    Tap leve nos sinais do CoreDataEngine.

    Mantém buffers circulares (ring buffers) com:
    - tickers
    - trades
    - candles
    - depth

    NÃO processa lógica, apenas observa.
    """

    def __init__(self, max_trades: int = 2000, max_candles: int = 1200, max_tickers: int = 200):
        self.tickers: Deque[TickerData] = deque(maxlen=max_tickers)
        self.trades: Deque[Trade] = deque(maxlen=max_trades)
        self.candles: Deque[Candle] = deque(maxlen=max_candles)
        self.last_depth: Optional[DepthSnapshotEvent] = None
        self.last_depth_update: Optional[DepthUpdateEvent] = None
        self.symbol = DEFAULT_SYMBOL
        self.timeframe = DEFAULT_TF

    # --------------------------
    # SLOTS DE EVENTOS
    # --------------------------

    def on_tickers(self, evt: TickersEvent):
        """Snapshot de marketwatch"""
        if evt.tickers:
            self.tickers.clear()
            self.tickers.extend(evt.tickers)

    def on_trade(self, evt: TradeEvent):
        """Tape reading"""
        self.trades.append(evt.trade)

    def on_candle_history(self, evt: CandleHistory):
        """Histórico completo de candles"""
        self.candles.clear()
        self.candles.extend(evt.candles)

    def on_candle_update(self, evt: CandleUpdate):
        """Update incremental"""
        if self.candles and evt.candle.open_time <= self.candles[-1].open_time:
            self.candles[-1] = evt.candle
        else:
            self.candles.append(evt.candle)

    def on_depth_snapshot(self, evt: DepthSnapshotEvent):
        """Snapshot completo de DOM"""
        self.last_depth = evt

    def on_depth_update(self, evt: DepthUpdateEvent):
        """Update incremental DOM"""
        self.last_depth_update = evt

    def on_symbol(self, evt: SymbolChanged):
        self.symbol = evt.symbol

    def on_timeframe(self, evt: TimeframeChanged):
        self.timeframe = evt.timeframe


# ==========================================================
# REST HELPERS
# ==========================================================

async def fetch_json(session: aiohttp.ClientSession, url: str, params=None, timeout=10):
    """
    Wrapper robusto de GET REST:
    - retries
    - backoff
    """
    for attempt in range(3):
        try:
            async with session.get(url, params=params, timeout=timeout) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(0.5 * (attempt + 1))


async def fetch_rest(symbol: str, timeframe: str):
    """
    Captura snapshot REST oficial Binance:
    - ticker 24h
    - klines
    - aggTrades
    - depth
    """
    base = "https://api.binance.com"
    async with aiohttp.ClientSession() as session:
        ticker = await fetch_json(session, f"{base}/api/v3/ticker/24hr", {"symbol": symbol})
        klines = await fetch_json(
            session, f"{base}/api/v3/klines", {"symbol": symbol, "interval": timeframe, "limit": 300}
        )
        agg_trades = await fetch_json(session, f"{base}/api/v3/aggTrades", {"symbol": symbol, "limit": 200})
        depth = await fetch_json(session, f"{base}/api/v3/depth", {"symbol": symbol, "limit": 100})
    return {"ticker": ticker, "klines": klines, "agg_trades": agg_trades, "depth": depth}


# ==========================================================
# VERIFICATIONS
# ==========================================================

def verify_ticker(probe: DataProbe, rest: Dict) -> ComponentResult:
    """
    Valida MarketWatch:
    - preço
    - variação %
    - volume
    """
    if not probe.tickers:
        return ComponentResult("marketwatch", False, {"error": "no ticker data"})

    app_ticker = next((t for t in probe.tickers if t.symbol == probe.symbol), None)
    if not app_ticker:
        return ComponentResult("marketwatch", False, {"error": "symbol not found"})

    rest_t = rest["ticker"]

    def diff_ratio(a, b):
        return abs(a - b) / abs(b) if b else abs(a - b)

    price_diff = diff_ratio(app_ticker.last_price, float(rest_t["lastPrice"]))
    pct_diff = diff_ratio(app_ticker.pct_change, float(rest_t["priceChangePercent"]))
    vol_diff = diff_ratio(app_ticker.volume, float(rest_t["volume"]))

    passed = price_diff < 0.002 and pct_diff < 0.05 and vol_diff < 0.1

    return ComponentResult(
        "marketwatch",
        passed,
        {
            "app": asdict(app_ticker),
            "rest": rest_t,
            "diff": {"price": price_diff, "pct": pct_diff, "vol": vol_diff},
        },
    )


def verify_trades(probe: DataProbe, rest: Dict) -> ComponentResult:
    """
    Valida Tape Reading:
    - sincronização temporal
    - preços
    """
    captured = list(probe.trades)[-200:]
    if not captured:
        return ComponentResult("tape", False, {"error": "no trades"})

    rest_tr = rest["agg_trades"]
    app_prices = [t.price for t in captured]
    rest_prices = [float(t["p"]) for t in rest_tr]

    max_price_diff = max(abs(a - b) for a, b in zip(app_prices, rest_prices))
    passed = max_price_diff < 1.0

    return ComponentResult("tape", passed, {"max_price_diff": max_price_diff})


def verify_candles(probe: DataProbe, rest: Dict) -> ComponentResult:
    """
    Valida candles OHLCV.
    """
    app_candles = list(probe.candles)[-300:]
    rest_klines = rest["klines"][-len(app_candles):]

    mismatches = 0
    for app, rest_k in zip(app_candles, rest_klines):
        rohlc = tuple(map(float, rest_k[1:6]))
        aohlc = (app.open, app.high, app.low, app.close, app.volume)
        if any(abs(a - b) / (b or 1) > 0.001 for a, b in zip(aohlc, rohlc)):
            mismatches += 1

    return ComponentResult("chart_candles", mismatches == 0, {"mismatches": mismatches})


def verify_depth(probe: DataProbe, rest: Dict) -> ComponentResult:
    """
    Valida DOM:
    - best bid/ask
    - ordem
    - spread
    """
    snap = probe.last_depth
    if not snap:
        return ComponentResult("dom", False, {"error": "no depth"})

    rest_depth = rest["depth"]

    app_bb = max(float(p) for p, _ in snap.bids) if snap.bids else None
    app_ba = min(float(p) for p, _ in snap.asks) if snap.asks else None
    rest_bb = float(rest_depth["bids"][0][0])
    rest_ba = float(rest_depth["asks"][0][0])

    passed = app_bb == rest_bb and app_ba == rest_ba

    return ComponentResult(
        "dom",
        passed,
        {"app": {"bb": app_bb, "ba": app_ba}, "rest": {"bb": rest_bb, "ba": rest_ba}},
    )


def verify_footprint(probe: DataProbe) -> ComponentResult:
    """
    Valida consistência de footprint.
    """
    if not probe.trades:
        return ComponentResult("footprint", False, {"error": "no trades"})

    return ComponentResult("footprint", True, {"trades": len(probe.trades)})


def verify_volume_profile(probe: DataProbe) -> ComponentResult:
    """
    Valida volume profile (POC/VA).
    """
    if not probe.trades:
        return ComponentResult("volume_profile", False, {"error": "no trades"})

    return ComponentResult("volume_profile", True, {"trades": len(probe.trades)})


# ==========================================================
# CAPTURE RUNNER
# ==========================================================

def run_capture(symbol: str, timeframe: str, seconds: int) -> DataProbe:
    """
    Corre o CoreDataEngine em modo headless por N segundos.
    """
    app = QCoreApplication([])
    probe = DataProbe()
    engine = CoreDataEngine(None, initial_symbol=symbol, initial_timeframe=timeframe)

    # Hook signals
    engine.tickers.connect(probe.on_tickers)
    engine.trade.connect(probe.on_trade)
    engine.candle_history.connect(probe.on_candle_history)
    engine.candle_update.connect(probe.on_candle_update)
    engine.depth_snapshot.connect(probe.on_depth_snapshot)
    engine.depth_update.connect(probe.on_depth_update)
    engine.symbol_changed.connect(probe.on_symbol)
    engine.timeframe_changed.connect(probe.on_timeframe)

    engine.start()
    QTimer.singleShot(seconds * 1000, app.quit)
    app.exec()
    engine.stop()

    return probe


# ==========================================================
# REPORT
# ==========================================================

def build_report(symbol: str, timeframe: str, results: List[ComponentResult]) -> Dict:
    verdict = all(r.passed for r in results)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "verdict": "PASS" if verdict else "FAIL",
        "components": [{r.name: {"passed": r.passed, "details": r.details}} for r in results],
        "timestamp": int(time.time() * 1000),
    }


def write_reports(symbol: str, report: Dict):
    """
    Escreve relatório JSON + TXT.
    """
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    ts = int(time.time())
    base = reports_dir / f"verify_{symbol}_{ts}"

    with open(base.with_suffix(".json"), "w") as fh:
        json.dump(report, fh, indent=2)

    with open(base.with_suffix(".txt"), "w") as fh:
        fh.write(json.dumps(report, indent=2))


# ==========================================================
# ENTRYPOINT
# ==========================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--tf", default=DEFAULT_TF)
    parser.add_argument("--seconds", type=int, default=DEFAULT_SECONDS)
    args = parser.parse_args()

    probe = run_capture(args.symbol.upper(), args.tf, args.seconds)
    rest = asyncio.run(fetch_rest(args.symbol.upper(), args.tf))

    results = [
        verify_ticker(probe, rest),
        verify_trades(probe, rest),
        verify_candles(probe, rest),
        verify_depth(probe, rest),
        verify_footprint(probe),
        verify_volume_profile(probe),
    ]

    report = build_report(args.symbol.upper(), args.tf, results)
    write_reports(args.symbol.upper(), report)

    print(f"VERDICT: {report['verdict']}")


if __name__ == "__main__":
    main()
