"""
Verification suite for OmniFlow Terminal data vs Binance REST snapshots.

Runs headless: spins up CoreDataEngine, captures events for a window, then
cross-checks against REST endpoints and writes JSON + TXT reports.
"""

import argparse
import asyncio
import json
import os
import time
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

import aiohttp
from PySide6.QtCore import QCoreApplication, QTimer

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



DEFAULT_SECONDS = 90
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_TF = "1m"


@dataclass
class ComponentResult:
    name: str
    passed: bool
    details: Dict


class DataProbe:
    """
    Lightweight tap on CoreDataEngine signals. Stores last-N events in ring buffers.
    """

    def __init__(self, max_trades: int = 2000, max_candles: int = 1200, max_tickers: int = 200):
        self.tickers: Deque[TickerData] = deque(maxlen=max_tickers)
        self.trades: Deque[Trade] = deque(maxlen=max_trades)
        self.candles: Deque[Candle] = deque(maxlen=max_candles)
        self.last_depth: Optional[DepthSnapshotEvent] = None
        self.last_depth_update: Optional[DepthUpdateEvent] = None
        self.symbol = DEFAULT_SYMBOL
        self.timeframe = DEFAULT_TF

    # Slots
    def on_tickers(self, evt: TickersEvent):
        if evt.tickers:
            self.tickers.clear()
            self.tickers.extend(evt.tickers)

    def on_trade(self, evt: TradeEvent):
        self.trades.append(evt.trade)

    def on_candle_history(self, evt: CandleHistory):
        # history replaces buffer
        self.candles.clear()
        self.candles.extend(evt.candles)

    def on_candle_update(self, evt: CandleUpdate):
        # append or replace last
        if self.candles and evt.candle.open_time <= self.candles[-1].open_time:
            self.candles[-1] = evt.candle
        else:
            self.candles.append(evt.candle)

    def on_depth_snapshot(self, evt: DepthSnapshotEvent):
        self.last_depth = evt

    def on_depth_update(self, evt: DepthUpdateEvent):
        self.last_depth_update = evt

    def on_symbol(self, evt: SymbolChanged):
        self.symbol = evt.symbol

    def on_timeframe(self, evt: TimeframeChanged):
        self.timeframe = evt.timeframe


# REST helpers
async def fetch_json(session: aiohttp.ClientSession, url: str, params=None, timeout=10):
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
    base = "https://api.binance.com"
    kline_limit = 300
    agg_limit = 200
    depth_limit = 100
    async with aiohttp.ClientSession() as session:
        ticker = await fetch_json(session, f"{base}/api/v3/ticker/24hr", {"symbol": symbol})
        klines = await fetch_json(
            session, f"{base}/api/v3/klines", {"symbol": symbol, "interval": timeframe, "limit": kline_limit}
        )
        agg_trades = await fetch_json(session, f"{base}/api/v3/aggTrades", {"symbol": symbol, "limit": agg_limit})
        depth = await fetch_json(session, f"{base}/api/v3/depth", {"symbol": symbol, "limit": depth_limit})
    return {"ticker": ticker, "klines": klines, "agg_trades": agg_trades, "depth": depth}


# Verification functions
def verify_ticker(probe: DataProbe, rest: Dict) -> ComponentResult:
    details = {}
    if not probe.tickers:
        return ComponentResult("marketwatch", False, {"error": "no ticker data captured"})
    app_ticker = next((t for t in probe.tickers if t.symbol == probe.symbol.upper()), None)
    if not app_ticker:
        return ComponentResult("marketwatch", False, {"error": f"ticker {probe.symbol} not in capture"})
    rest_t = rest["ticker"]
    # tolerances
    def diff_ratio(a, b):
        if b == 0:
            return abs(a - b)
        return abs(a - b) / abs(b)

    price_diff = diff_ratio(app_ticker.last_price, float(rest_t["lastPrice"]))
    pct_diff = diff_ratio(app_ticker.pct_change, float(rest_t["priceChangePercent"]))
    vol_diff = diff_ratio(app_ticker.volume, float(rest_t["volume"]))
    passed = price_diff < 0.002 and pct_diff < 0.05 and vol_diff < 0.1
    details.update(
        {
            "app": {"last": app_ticker.last_price, "pct": app_ticker.pct_change, "vol": app_ticker.volume},
            "rest": {"last": float(rest_t["lastPrice"]), "pct": float(rest_t["priceChangePercent"]), "vol": float(rest_t["volume"])},
            "diff": {"price_rel": price_diff, "pct_rel": pct_diff, "vol_rel": vol_diff},
            "tolerance": ["price_rel<0.2%", "pct_rel<5%", "vol_rel<10%"],
        }
    )
    return ComponentResult("marketwatch", passed, details)


def verify_trades(probe: DataProbe, rest: Dict) -> ComponentResult:
    details = {}
    captured = list(probe.trades)[-200:]
    rest_tr = rest["agg_trades"]
    if not captured:
        return ComponentResult("tape", False, {"error": "no trades captured"})
    # map by id
    app_ids = [t.ts for t in captured]
    rest_ids = [t["T"] for t in rest_tr]
    app_prices = [t.price for t in captured]
    rest_prices = [float(t["p"]) for t in rest_tr]
    id_overlap = len(set(app_ids).intersection(rest_ids))
    missing = len(rest_ids) - id_overlap
    extra = len(app_ids) - id_overlap
    max_drift_ms = max(abs(ai - ri) for ai, ri in zip(app_ids[:len(rest_ids)], rest_ids[:len(app_ids)]))
    price_mismatch = max(abs(a - b) for a, b in zip(app_prices[:len(rest_prices)], rest_prices[:len(app_prices)]))
    passed = id_overlap > 50 and price_mismatch < 1.0
    details.update(
        {
            "captured": len(captured),
            "rest": len(rest_tr),
            "overlap_ids": id_overlap,
            "missing_vs_rest": missing,
            "extra_vs_rest": extra,
            "max_time_drift_ms": max_drift_ms,
            "max_price_diff": price_mismatch,
        }
    )
    return ComponentResult("tape", passed, details)


def verify_candles(probe: DataProbe, rest: Dict) -> ComponentResult:
    details = {"mismatches": []}
    app_candles = list(probe.candles)[-300:]
    rest_klines = rest["klines"][-len(app_candles) :]
    if not app_candles:
        return ComponentResult("chart_candles", False, {"error": "no candles captured"})
    mismatches = 0
    for app, rest_k in zip(app_candles, rest_klines):
        ts = int(rest_k[0])
        rohlc = (float(rest_k[1]), float(rest_k[2]), float(rest_k[3]), float(rest_k[4]), float(rest_k[5]))
        aohlc = (app.open, app.high, app.low, app.close, app.volume)
        diffs = [abs(a - b) for a, b in zip(aohlc, rohlc)]
        if any(d > 1e-6 and d / (b or 1) > 0.001 for d, b in zip(diffs, rohlc)):
            mismatches += 1
            details["mismatches"].append({"ts": ts, "app": aohlc, "rest": rohlc, "diffs": diffs})
    passed = mismatches == 0
    details["checked"] = len(app_candles)
    details["mismatch_count"] = mismatches
    return ComponentResult("chart_candles", passed, details)


def verify_depth(probe: DataProbe, rest: Dict) -> ComponentResult:
    details = {}
    snap = probe.last_depth
    if not snap:
        return ComponentResult("dom", False, {"error": "no depth snapshot captured"})
    rest_depth = rest["depth"]
    def top(levels, reverse=False):
        return sorted([(float(p), float(q)) for p, q in levels], key=lambda x: x[0], reverse=reverse)[:5]
    app_bids = top(snap.bids, reverse=True)
    app_asks = top(snap.asks, reverse=False)
    rest_bids = top(rest_depth["bids"], reverse=True)
    rest_asks = top(rest_depth["asks"], reverse=False)
    def best_bid_ask(levels, reverse):
        return levels[0][0] if levels else None
    bb_app, ba_app = best_bid_ask(app_bids, True), best_bid_ask(app_asks, False)
    bb_rest, ba_rest = best_bid_ask(rest_bids, True), best_bid_ask(rest_asks, False)
    spread_ok = ba_app is None or bb_app is None or ba_app >= bb_app
    best_match = bb_app == bb_rest and ba_app == ba_rest
    order_ok = all(app_bids[i][0] > app_bids[i + 1][0] for i in range(len(app_bids) - 1)) and all(
        app_asks[i][0] < app_asks[i + 1][0] for i in range(len(app_asks) - 1)
    )
    passed = spread_ok and order_ok and best_match
    details.update(
        {
            "app_top": {"bids": app_bids, "asks": app_asks},
            "rest_top": {"bids": rest_bids, "asks": rest_asks},
            "best_match": best_match,
            "spread_ok": spread_ok,
            "order_ok": order_ok,
        }
    )
    return ComponentResult("dom", passed, details)


def verify_volume(probe: DataProbe, rest: Dict) -> ComponentResult:
    details = {"mismatches": []}
    app_candles = list(probe.candles)[-200:]
    rest_klines = rest["klines"][-len(app_candles) :]
    if not app_candles:
        return ComponentResult("candle_volume", False, {"error": "no candles"})
    mismatches = 0
    for app, rest_k in zip(app_candles, rest_klines):
        rest_vol = float(rest_k[5])
        if abs(app.volume - rest_vol) / (rest_vol or 1) > 0.01:
            mismatches += 1
            details["mismatches"].append({"ts": rest_k[0], "app": app.volume, "rest": rest_vol})
    passed = mismatches == 0
    details["checked"] = len(app_candles)
    details["mismatch_count"] = mismatches
    return ComponentResult("candle_volume", passed, details)


def verify_footprint(probe: DataProbe) -> ComponentResult:
    details = {}
    trades = list(probe.trades)
    if not trades:
        return ComponentResult("footprint", False, {"error": "no trades"})
    bucketed: Dict[float, Dict[str, float]] = {}
    for t in trades[-500:]:
        price = round(t.price, 2)
        cell = bucketed.setdefault(price, {"buy": 0.0, "sell": 0.0})
        if t.side.lower() == "buy":
            cell["buy"] += t.qty
        else:
            cell["sell"] += t.qty
    total_buy = sum(v["buy"] for v in bucketed.values())
    total_sell = sum(v["sell"] for v in bucketed.values())
    details.update({"buckets": len(bucketed), "total_buy": total_buy, "total_sell": total_sell})
    return ComponentResult("footprint", True, details)


def verify_volume_profile(probe: DataProbe) -> ComponentResult:
    details = {}
    trades = list(probe.trades)
    if not trades:
        return ComponentResult("volume_profile", False, {"error": "no trades"})
    buckets: Dict[float, float] = {}
    for t in trades[-2000:]:
        price = round(t.price, 2)
        buckets[price] = buckets.get(price, 0.0) + t.qty
    if not buckets:
        return ComponentResult("volume_profile", False, {"error": "empty buckets"})
    poc_price = max(buckets.items(), key=lambda kv: kv[1])[0]
    sorted_levels = sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(buckets.values())
    acc = 0.0
    selected = []
    for price, vol in sorted_levels:
        acc += vol
        selected.append(price)
        if acc >= total * 0.7:
            break
    vah, val = max(selected), min(selected)
    details.update({"levels": len(buckets), "poc": poc_price, "vah": vah, "val": val, "total": total})
    return ComponentResult("volume_profile", True, details)


def run_capture(symbol: str, timeframe: str, seconds: int) -> DataProbe:
    app = QCoreApplication([])
    probe = DataProbe()
    engine = CoreDataEngine(None, initial_symbol=symbol, initial_timeframe=timeframe)
    # Connect signals
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
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    ts = int(time.time())
    base = reports_dir / f"verify_{symbol}_{ts}"
    json_path = base.with_suffix(".json")
    txt_path = base.with_suffix(".txt")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    # simple text render
    lines = [f"Verify report for {symbol}", f"Verdict: {report['verdict']}", ""]
    for comp in report["components"]:
        name, payload = next(iter(comp.items()))
        lines.append(f"[{name}] {'PASS' if payload['passed'] else 'FAIL'}")
        lines.append(json.dumps(payload["details"], indent=2))
        lines.append("")
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return json_path, txt_path


def main():
    parser = argparse.ArgumentParser(description="External verification suite for OmniFlow Terminal vs Binance REST")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--tf", "--timeframe", dest="timeframe", default=DEFAULT_TF)
    parser.add_argument("--seconds", type=int, default=DEFAULT_SECONDS, help="capture window seconds")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    timeframe = args.timeframe

    probe = run_capture(symbol, timeframe, args.seconds)
    rest = asyncio.run(fetch_rest(symbol, timeframe))

    results = [
        verify_ticker(probe, rest),
        verify_trades(probe, rest),
        verify_candles(probe, rest),
        verify_volume(probe, rest),
        verify_depth(probe, rest),
        verify_footprint(probe),
        verify_volume_profile(probe),
    ]
    report = build_report(symbol, timeframe, results)
    json_path, txt_path = write_reports(symbol, report)
    print(f"Report written: {json_path}")
    print(f"Text summary: {txt_path}")
    print(f"Verdict: {report['verdict']}")


if __name__ == "__main__":
    main()
