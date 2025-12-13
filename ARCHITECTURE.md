# OmniFlow Terminal — Core Data Engine (Unified)

## Goal
Single source of truth for market data (history + realtime) across the app. UI never talks directly to providers; it consumes normalized Qt signals emitted from `CoreDataEngine`.

## Module Layout
```
core/data_engine/
  core_engine.py        # Singleton-like orchestrator, owns symbol/timeframe, emits Qt signals
  events.py             # Normalized event dataclasses (CANDLE_HISTORY, CANDLE_UPDATE, TRADE, DEPTH_*)
  symbol_state.py       # Thread-safe symbol guard
  timeframe_state.py    # Thread-safe timeframe guard
  cache_manager.py      # In-memory cache (candles/trades/depth), ready for future disk persistence
  providers/
    binance_provider.py # REST + WS (klines/trades/depth/tickers) with backfill + live merge
```

## Data Flow (ASCII)
```
          +-------------------+          +---------------------------+
          |   UI widgets      |          |  CoreDataEngine (Qt)      |
          |   (Chart/Tape/MW) |<---------|  Qt Signals:              |
          +-------------------+          |  - symbol_changed         |
                   ^                     |  - timeframe_changed      |
                   |                     |  - tickers                |
                   |                     |  - candle_history         |
                   |                     |  - candle_update          |
                   |                     |  - trade                  |
                   |                     |  - depth_snapshot/update  |
                   |                     +-------------^-------------+
                   |                                   |
                   | emits Qt signals (queued)         | callbacks
                   |                                   |
          +--------+-----------------------------------+--------+
          |       BinanceProvider (async, worker thread)        |
          | - REST klines backfill (300-1000)                   |
          | - WS klines/trades/depth diffs                      |
          | - WS !ticker@arr for MarketWatch                    |
          | - Depth snapshot -> diffs merge -> throttled emit   |
          +-----------------------------------------------------+
```

## Key Behaviors
- **Backfill + realtime merge**: On symbol/timeframe change, fetch klines history (REST), emit `CANDLE_HISTORY`, then start kline/trade/depth websockets; kline updates emit `CANDLE_UPDATE` with closed/in-flight flag.
- **Depth consistency**: REST snapshot seeds the book; diff stream applies incremental updates with basic gap detection and resync.
- **Tickers**: `!ticker@arr` filtered by watchlist feeds MarketWatch via `TickersEvent`.
- **Thread-safety**: Networking runs on an asyncio loop in a worker thread; signals emitted from that thread are queued by Qt, keeping UI updates on the main thread.
- **Caching**: In-memory caches keep recent candles/trades/depth per (symbol, timeframe) to avoid reloads and prepare for future disk persistence.
- **Singleton usage**: One `CoreDataEngine` instance created in `ui/main_window.py`, reused across panels.

## Wiring in UI
- `MainWindow` now instantiates `CoreDataEngine` and connects:
  - MarketWatch ⇐ `tickers`
  - Chart ⇐ `candle_history`, `candle_update`
  - Tape ⇐ `trade`
  - Symbol changes: `MarketWatch` → `AppState` → `CoreDataEngine.set_symbol`; engine echoes `symbol_changed` back to update Chart/Tape/AppState.
  - Timeframe changes: `ChartPanel.timeframe_changed` → `CoreDataEngine.set_timeframe`.

## Extensibility Notes
- To add new providers/brokers, add under `core/data_engine/providers/` and plug into `CoreDataEngine` with the same normalized events.
- To persist caches, extend `cache_manager.py` to mirror in-memory state to disk without changing UI contracts.
- Advanced analytics (footprint, VP, microstructure) can subscribe to the same events without modifying provider code.
