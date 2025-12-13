# OmniFlow Verification Suite

Headless cross-check of OmniFlow Terminal data (via CoreDataEngine) against Binance REST snapshots. Generates JSON + text reports with PASS/FAIL per component.

## Endpoints used
- `/api/v3/ticker/24hr` — tickers (lastPrice, priceChangePercent, volume)
- `/api/v3/klines` — OHLCV for timeframe
- `/api/v3/aggTrades` — recent aggregated trades
- `/api/v3/depth` — order book snapshot (limit=100)

## How to run
```
python -m tools.verify_suite --symbol BTCUSDT --tf 1m --seconds 120
```
Outputs to `reports/verify_<symbol>_<ts>.json` and `.txt`.

## What is checked
- **MarketWatch (tickers)**: app ticker vs REST 24hr (price, pct change, volume) with relaxed tolerances for latency and rounding.
- **Time & Sales (aggTrades)**: captured trades vs REST aggTrades (ordering, overlap, max time drift, price differences).
- **Price Chart / Candles**: OHLCV for last ~300 bars vs REST klines; forming bar allowed to drift.
- **Candle Volume**: closed-bar volume vs REST.
- **DOM Ladder**: best bid/ask vs REST depth snapshot; invariants (no negative qty, bid desc/ask asc, spread >= 0).
- **Footprint**: aggregates captured trades into price buckets (recent window) and reports totals.
- **Volume Profile**: trade-derived histogram totals, POC, VAH/VAL (70%).

## Tolerances & limitations
- Latency: REST snapshots and WS streams are not time-aligned; small diffs are acceptable.
- Current/forming candle and live depth may drift; verification focuses on closed bars and snapshot consistency.
- Volume Profile and Footprint rely on trades captured during the window; very short windows may undercount.
- AggTrades overlap is heuristic; perfect 1:1 match is not guaranteed due to timing.

## Interpreting reports
- JSON: machine-readable per-component results and metrics.
- TXT: human summary with PASS/FAIL per component and detail blobs.
- Verdict is PASS only if all components pass. Look at mismatch counts/diffs for diagnostics.
