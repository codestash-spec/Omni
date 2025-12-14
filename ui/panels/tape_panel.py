from collections import deque
from datetime import datetime
import logging
import time

from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.theme import colors, typography
from core.data_engine.models import Trade



class TapePanel(QWidget):
    """
    Time & Sales / Tape Reading panel.
    - Size modes: BASE (raw), QUOTE (USD), COMPACT (K/M); default QUOTE.
    - Flags: Block, Sweep, Iceberg, Absorb using lightweight heuristics.
    - Filters: Aggressive Only (min notional), Block Trades only.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TapePanel")
        self._logger = logging.getLogger(__name__)

        self._trades: deque[dict] = deque(maxlen=120)
        self._live_buckets: dict[str, dict] = {}
        self._pending: deque[Trade] = deque(maxlen=500)
        self._recent_for_flags: deque[Trade] = deque(maxlen=400)
        self._settings = QSettings("OmniFlow", "TapePanel")
        self._load_settings()

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(50)  # ~20 FPS
        self._flush_timer.timeout.connect(self._flush_pending)
        self._flush_timer.start()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        lbl = QLabel("Tape Reading")
        lbl.setFont(typography.inter(11, QFont.DemiBold))
        header.addWidget(lbl)
        header.addStretch()

        # Hidden toggles; values come from Settings dialog (QSettings-backed)
        self.aggr_only = QCheckBox("Aggressive Only")
        self.blocks_only = QCheckBox("Block Trades")
        self.aggr_only.setVisible(False)
        self.blocks_only.setVisible(False)
        layout.addLayout(header)

        self.table = QTableWidget(12, 5)
        self.table.setHorizontalHeaderLabels(["Time", "Price", "Size", "Side", "Flags"])
        header_view = self.table.horizontalHeader()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        header_view.setMinimumSectionSize(60)
        header_view.resizeSection(0, 110)  # Time
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Price
        header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Size
        header_view.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Side
        header_view.setSectionResizeMode(4, QHeaderView.Stretch)  # Flags flex
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        self.table.setMouseTracking(True)
        self.table.setStyleSheet(
            """
            QTableWidget::item:selected { background-color: rgba(80,120,200,80); }
            QTableWidget::item:hover { background-color: rgba(255,255,255,25); }
            """
        )
        layout.addWidget(self.table)

    # --------------------------
    # Settings load / reload
    # --------------------------
    def _load_settings(self):
        self._size_mode = str(self._settings.value("size_mode", "QUOTE") or "QUOTE")
        self._min_notional_filter = float(self._settings.value("min_notional_filter", 0.0))
        self._block_threshold = float(self._settings.value("block_threshold", 100_000.0))
        self._aggr_only_enabled = self._as_bool(self._settings.value("aggr_only", False))
        self._blocks_only_enabled = self._as_bool(self._settings.value("blocks_only", False))
        self._flags_enabled = self._as_bool(self._settings.value("flags_enabled", False))
        self._acc_interval_ms = int(self._settings.value("accumulation_interval_ms", 0))

        self._iceberg_window_ms = int(self._settings.value("iceberg_window_ms", 400))
        self._iceberg_count = int(self._settings.value("iceberg_count", 5))

        self._sweep_window_ms = int(self._settings.value("sweep_window_ms", 300))
        self._sweep_price_levels = int(self._settings.value("sweep_price_levels", 4))
        self._sweep_min_notional = float(self._settings.value("sweep_min_notional", 5_000.0))
        self._sweep_min_price_diff = float(self._settings.value("sweep_min_price_diff", 1.0))

        self._absorb_window_ms = int(self._settings.value("absorb_window_ms", 800))
        self._absorb_volume = float(self._settings.value("absorb_volume", 20_000.0))

    def reload_settings(self):
        self._load_settings()
        self.aggr_only.setChecked(self._aggr_only_enabled)
        self.blocks_only.setChecked(self._blocks_only_enabled)
        self.populate(list(self._trades))

    # --------------------------
    # Rendering
    # --------------------------
    def populate(self, rows: list[dict]):
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            time_item = QTableWidgetItem(row["time"])
            price_item = QTableWidgetItem(f"{row['price']:.2f}")
            size_item = QTableWidgetItem(str(row["size"]))
            side_item = QTableWidgetItem(row["side"])
            flags_item = QTableWidgetItem(row.get("flags", ""))

            if row["side"] == "Buy":
                side_color = colors.ACCENT_GREEN
            elif row["side"] == "Sell":
                side_color = colors.ACCENT_RED
            else:
                side_color = colors.MUTED

            price_item.setForeground(QColor(side_color))
            side_item.setForeground(QColor(side_color))

            for item in [time_item, price_item, size_item, side_item, flags_item]:
                item.setFont(typography.mono(10))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if item in (price_item, size_item, flags_item) else Qt.AlignCenter)
            # Size stands out slightly
            sfont = size_item.font()
            sfont.setBold(True)
            size_item.setFont(sfont)

            self.table.setItem(r, 0, time_item)
            self.table.setItem(r, 1, price_item)
            self.table.setItem(r, 2, size_item)
            self.table.setItem(r, 3, side_item)
            self.table.setItem(r, 4, flags_item)

            # Background layering: base dark, side tint, flags override
            tint = QColor(side_color)
            tint.setAlpha(30)
            row_bg = tint if not row.get("flags") else QColor(0, 0, 0)
            for c in range(self.table.columnCount()):
                self.table.item(r, c).setBackground(row_bg)
            if "notional_tooltip" in row:
                size_item.setToolTip(row["notional_tooltip"])
            if "flags_tooltip" in row:
                flags_item.setToolTip(row["flags_tooltip"])

            flag_names = row.get("flag_names", [])
            if "Block" in flag_names:
                price_item.setForeground(QColor(colors.HIGHLIGHT))
            if "Sweep" in flag_names:
                f = price_item.font()
                f.setBold(True)
                price_item.setFont(f)
            if "Absorb" in flag_names:
                flags_item.setForeground(QColor(colors.HIGHLIGHT))
            if row.get("flags"):
                flags_item.setBackground(QColor(colors.HIGHLIGHT))
                flags_item.setForeground(QColor(colors.BACKGROUND))
        self.table.setUpdatesEnabled(True)

    def update_data(self, rows):
        self.populate(rows)

    # --------------------------
    # Data ingestion
    # --------------------------
    def on_trade(self, trade: Trade):
        # Queue trades to avoid UI thrash
        self._pending.append(trade)

    def _flush_pending(self):
        if not self._pending:
            return
        max_batch = 100  # tighter limit per frame to avoid UI stalls on bursts
        time_budget = 0.01  # ~10ms per flush
        start = time.perf_counter()
        new_rows: list[dict] = []
        finalized: list[dict] = []
        live_rows: list[dict] = []
        use_acc = self._acc_interval_ms > 0

        processed = 0
        while self._pending and processed < max_batch:
            trade = self._pending.popleft()
            processed += 1
            ts = datetime.utcfromtimestamp(trade.ts / 1000)
            formatted = ts.strftime("%H:%M:%S.%f")[:-3]
            notional = trade.price * trade.qty
            if not (notional >= 0 and trade.price >= 0 and trade.qty >= 0):
                self._logger.debug("Tape notional anomaly price=%.6f qty=%.6f notional=%.6f", trade.price, trade.qty, notional)
            calc_notional = trade.price * trade.qty
            if abs(calc_notional - notional) > max(1e-6, abs(notional) * 0.005):
                # Validate quote_size ~ base_size * price within 0.5%
                self._logger.warning(
                    "Tape notional deviation >0.5%% price=%.6f qty=%.6f calc=%.6f stored=%.6f",
                    trade.price,
                    trade.qty,
                    calc_notional,
                    notional,
                )

            flags = self._derive_flags(trade, notional)
            # Keep recent trades for future flag derivation even if filtered out
            self._recent_for_flags.append(trade)

            if (self.blocks_only.isChecked() or self._blocks_only_enabled) and "Block" not in flags:
                continue
            if (self.aggr_only.isChecked() or self._aggr_only_enabled) and notional < self._min_notional_filter:
                continue

            if use_acc:
                bucket_id = trade.ts // self._acc_interval_ms
                live = self._live_buckets.get(trade.side)
                if live and live["bucket"] != bucket_id:
                    self._finalize_bucket(live, finalized)
                    self._live_buckets.pop(trade.side, None)
                    live = None
                if not live:
                    live = {
                        "bucket": bucket_id,
                        "qty": 0.0,
                        "notional": 0.0,
                        "vw_sum": 0.0,
                        "ts": trade.ts,
                        "side": trade.side,
                        "flags": set(),
                    }
                live["qty"] += trade.qty
                live["notional"] += notional
                live["vw_sum"] += trade.price * trade.qty
                live["ts"] = max(live["ts"], trade.ts)
                live["flags"].update(flags)
                self._live_buckets[trade.side] = live
            else:
                new_rows.append(self._make_row(formatted, trade.ts, trade.price, trade.qty, notional, trade.side, flags))
            if time.perf_counter() - start >= time_budget:
                break

        if use_acc:
            # finalize any live buckets older than current interval window for safety
            # (not strictly needed if buckets always replaced by newer)
            for side, live in list(self._live_buckets.items()):
                live_rows.append(self._make_row_from_bucket(live, live=True))
            finalized.sort(key=lambda r: r["ts"], reverse=True)
            for row in finalized:
                self._trades.appendleft(row)
            display_rows = live_rows + list(self._trades)
        else:
            new_rows.sort(key=lambda r: r["ts"], reverse=True)
            for row in new_rows:
                self._trades.appendleft(row)
            display_rows = list(self._trades)

        # keep newest (by ts) on top
        if len(self._trades) == self._trades.maxlen and (new_rows or finalized):
            self._logger.debug("Tape buffer full (%d); oldest entries dropped", self._trades.maxlen)
        self.populate(display_rows)
        latest = (new_rows or finalized or live_rows or [{}])[0]
        self._logger.debug(
            "Tape batch %d trades (latest=%s %.4f x %s) -> redraw %d rows in %.3fs",
            len(new_rows) if not use_acc else len(new_rows) + len(finalized) + len(live_rows),
            latest.get("side", "-"),
            latest.get("price", 0.0),
            latest.get("size", 0.0),
            len(display_rows),
            time.perf_counter() - start,
        )

    def set_symbol(self, symbol: str):
        self._logger.info("Tape symbol changed -> %s; clearing buffer", symbol)
        self._trades.clear()
        self._live_buckets.clear()
        self.populate([])

    # --------------------------
    # Flag heuristics
    # --------------------------
    def _derive_flags(self, trade: Trade, notional: float) -> list[str]:
        if not getattr(self, "_flags_enabled", False):
            return []
        """
        Heuristics (no new data calls):
        - Block: notional over threshold.
        - Iceberg: repeated small prints at same price within a short window.
        - Sweep: many price levels touched quickly with some size.
        - Absorption: large cumulative notional at the same price without price moving.
        """
        flags: list[str] = []
        if notional >= self._block_threshold:
            flags.append("Block")

        now_ms = trade.ts
        # Iceberg: multiple small hits at same price within window
        recent = [t for t in self._recent_for_flags if now_ms - t.ts <= self._iceberg_window_ms]
        same_price = [t for t in recent if abs(t.price - trade.price) < 1e-6]
        if len(same_price) >= self._iceberg_count and notional < self._block_threshold * 0.05:
            flags.append("Iceberg")

        # Sweep: unique price levels, quick burst, some range and notional
        recent_sweep = [t for t in self._recent_for_flags if now_ms - t.ts <= self._sweep_window_ms]
        prices = [t.price for t in recent_sweep]
        if prices:
            price_range = max(prices) - min(prices)
            unique_prices = {round(p, 2) for p in prices}
            sweep_notional = sum(t.price * t.qty for t in recent_sweep)
            if (
                len(unique_prices) >= self._sweep_price_levels
                and price_range >= self._sweep_min_price_diff
                and sweep_notional >= self._sweep_min_notional
            ):
                flags.append("Sweep")

        # Absorption: big volume at the same price, holding the level
        absorb_recent = [
            t for t in self._recent_for_flags if now_ms - t.ts <= self._absorb_window_ms and abs(t.price - trade.price) < 1e-6
        ]
        if sum(t.price * t.qty for t in absorb_recent) >= self._absorb_volume:
            flags.append("Absorb")

        return flags

    def _finalize_bucket(self, bucket: dict, collector: list[dict]):
        qty = bucket.get("qty", 0.0)
        notional = bucket.get("notional", 0.0)
        if qty <= 0:
            return
        vw_price = bucket.get("vw_sum", 0.0) / qty if qty else 0.0
        ts_ms = bucket.get("ts", 0)
        ts = datetime.utcfromtimestamp(ts_ms / 1000)
        formatted = ts.strftime("%H:%M:%S.%f")[:-3]
        flags = list(bucket.get("flags", []))
        collector.append(
            self._make_row(
                formatted,
                ts_ms,
                vw_price,
                qty,
                notional,
                bucket.get("side", "-"),
                flags,
            )
        )

    def _make_row_from_bucket(self, bucket: dict, live: bool = False) -> dict:
        qty = bucket.get("qty", 0.0)
        notional = bucket.get("notional", 0.0)
        vw_price = bucket.get("vw_sum", 0.0) / qty if qty else 0.0
        ts_ms = bucket.get("ts", 0)
        ts = datetime.utcfromtimestamp(ts_ms / 1000)
        formatted = ts.strftime("%H:%M:%S.%f")[:-3]
        flags = list(bucket.get("flags", []))
        row = self._make_row(formatted, ts_ms, vw_price, qty, notional, bucket.get("side", "-"), flags)
        if live:
            row["flags_tooltip"] = (row.get("flags_tooltip", "") + "; LIVE bucket").strip("; ")
        return row

    def _make_row(self, formatted_time: str, ts_ms: int, price: float, qty: float, notional: float, side: str, flags: list[str]) -> dict:
        tooltip_parts = []
        for f in flags:
            if f == "Block":
                tooltip_parts.append(f"Block trades over ${self._block_threshold:,.0f}")
            elif f == "Iceberg":
                tooltip_parts.append("Iceberg: repeated small prints at same price")
            elif f == "Sweep":
                tooltip_parts.append("Sweep: multiple price levels in a short window")
            elif f == "Absorb":
                tooltip_parts.append("Absorption: large volume, price holding")

        display_flags = " ".join(flags)
        size_tooltip = f"{qty:.6f} base\n${notional:,.2f}"
        size_display = self._format_size(qty, notional)
        return {
            "time": formatted_time,
            "ts": ts_ms,
            "price": price,
            "size": size_display,
            "side": side,
            "flags": display_flags,
            "flag_names": flags,
            "flags_tooltip": "; ".join(tooltip_parts) if tooltip_parts else "",
            "notional_tooltip": size_tooltip,
        }

    # --------------------------
    # Formatting helpers
    # --------------------------
    def _format_size(self, base_qty: float, notional: float) -> str:
        mode = self._size_mode
        if mode == "BASE":
            return f"{base_qty:.4f}"
        if mode == "COMPACT":
            val = notional
            if val < 1_000:
                return f"{val:.0f}"
            if val < 1_000_000:
                return f"{val/1_000:.1f}K"
            return f"{val/1_000_000:.2f}M"
        # default QUOTE
        return f"${notional:,.2f}"

    def _on_size_mode_changed(self, mode: str):
        self._size_mode = mode
        self._settings.setValue("size_mode", mode)
        self.populate(list(self._trades))

    def _as_bool(self, val) -> bool:
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        if isinstance(val, (int, float)):
            return val != 0
        s = str(val).strip().lower()
        return s in ("1", "true", "yes", "on")
