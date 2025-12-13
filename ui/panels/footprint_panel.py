import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Tuple, Optional

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.data_engine.events import TradeEvent, CandleHistory, CandleUpdate, TimeframeChanged, SymbolChanged
from data_engine.models import Trade
from ui.theme import colors, typography


@dataclass
class FootprintCell:
    price: float
    buy: float
    sell: float

    @property
    def delta(self) -> float:
        return self.buy - self.sell


class FootprintAggregator:
    def __init__(self):
        self.timeframe_ms = 60_000
        self.symbol = "BTCUSDT"
        self.cells: Dict[int, Dict[float, FootprintCell]] = {}
        self.trades: Deque[Trade] = deque(maxlen=5000)
        self.bucket_history = 4  # combine last N buckets for display

    def set_timeframe(self, tf: str):
        mapping = {
            "1m": 60_000,
            "5m": 300_000,
            "15m": 900_000,
            "1h": 3_600_000,
            "4h": 14_400_000,
            "1d": 86_400_000,
        }
        self.timeframe_ms = mapping.get(tf.lower(), 60_000)
        self.cells.clear()
        self.trades.clear()

    def set_symbol(self, symbol: str):
        self.symbol = symbol.upper()
        self.cells.clear()
        self.trades.clear()

    def add_candles(self, candles):
        for c in candles:
            self.cells.setdefault(c.open_time, {})

    def add_candle_update(self, candle, closed: bool):
        self.cells.setdefault(candle.open_time, {})

    def add_trade(self, trade: Trade):
        if trade.symbol.upper() != self.symbol:
            return
        self.trades.append(trade)
        bucket = (trade.ts // self.timeframe_ms) * self.timeframe_ms
        levels = self.cells.setdefault(bucket, {})
        price_level = round(trade.price, 2)
        cell = levels.get(price_level)
        if not cell:
            cell = FootprintCell(price=price_level, buy=0.0, sell=0.0)
            levels[price_level] = cell
        if trade.side.lower() == "buy":
            cell.buy += trade.qty
        else:
            cell.sell += trade.qty

    def latest_cells(self, depth: int = 18) -> List[FootprintCell]:
        if not self.cells:
            return []
        buckets = sorted(self.cells.keys())[-self.bucket_history :]
        combined: Dict[float, FootprintCell] = {}
        for b in buckets:
            for price, cell in self.cells.get(b, {}).items():
                tgt = combined.get(price)
                if not tgt:
                    combined[price] = FootprintCell(price=price, buy=cell.buy, sell=cell.sell)
                else:
                    tgt.buy += cell.buy
                    tgt.sell += cell.sell
        levels = [c for c in combined.values() if (c.buy + c.sell) > 0]
        levels.sort(key=lambda c: c.price, reverse=True)
        return levels[:depth]


class FootprintView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.row_height = 24
        self.headers = ["Price", "Buy Vol", "Sell Vol", "Delta"]
        self.font = typography.mono(10)

    def _populate(self, rows: List[FootprintCell]):
        self.scene.clear()
        cols = [80, 90, 90, 70]
        x_positions = []
        x = 0
        for c in cols:
            x_positions.append(x)
            x += c
        for header, x in zip(self.headers, x_positions):
            t = self.scene.addText(header, typography.inter(10, QFont.DemiBold))
            t.setDefaultTextColor(QColor(colors.MUTED))
            t.setPos(x + 4, 2)

        if not rows:
            self.setSceneRect(0, 0, sum(cols), 22 + self.row_height * 2)
            return

        max_vol = max((c.buy + c.sell) for c in rows) or 1.0
        for i, row in enumerate(rows):
            y = 22 + i * self.row_height
            buy_intensity = min(1.0, row.buy / max_vol)
            sell_intensity = min(1.0, row.sell / max_vol)
            buy_rect = QRectF(x_positions[1], y + 3, cols[1] * buy_intensity, self.row_height - 6)
            sell_rect = QRectF(
                x_positions[2] + (cols[2] * (1 - sell_intensity)), y + 3, cols[2] * sell_intensity, self.row_height - 6
            )
            self.scene.addRect(buy_rect, pen=QColor(colors.BACKGROUND), brush=QColor(colors.ACCENT_GREEN).lighter(120))
            self.scene.addRect(sell_rect, pen=QColor(colors.BACKGROUND), brush=QColor(colors.ACCENT_RED).lighter(120))

            imbalance = row.buy >= row.sell * 2 and row.buy > 0
            absorption = (row.buy + row.sell) > max_vol * 0.5 and abs(row.delta) < (row.buy + row.sell) * 0.1

            if imbalance:
                marker = self.scene.addEllipse(
                    x_positions[3] + cols[3] - 14,
                    y + 6,
                    8,
                    8,
                    pen=QColor(colors.HIGHLIGHT),
                    brush=QColor(colors.HIGHLIGHT),
                )
                marker.setToolTip("Imbalance: Buy >= 2x Sell")
            if absorption:
                bubble = self.scene.addEllipse(
                    x_positions[1] + cols[1] - 14,
                    y + 6,
                    8,
                    8,
                    pen=QColor(colors.ACCENT_GREEN),
                    brush=QColor(colors.ACCENT_GREEN),
                )
                bubble.setToolTip("Absorption: high volume, muted delta")

            values = [
                f"{row.price:.2f}",
                f"{row.buy:.2f}",
                f"{row.sell:.2f}",
                f"{row.delta:+.2f}",
            ]
            colors_list = [
                colors.TEXT,
                colors.ACCENT_GREEN,
                colors.ACCENT_RED,
                colors.ACCENT_GREEN if row.delta >= 0 else colors.ACCENT_RED,
            ]
            aligns = [1, 1, 2, 1]
            for idx, (val, color_hex, align) in enumerate(zip(values, colors_list, aligns)):
                txt = QGraphicsTextItem(str(val))
                txt.setFont(self.font)
                txt.setDefaultTextColor(QColor(color_hex))
                w = txt.boundingRect().width()
                xpos = x_positions[idx] + (cols[idx] - w) * (0.1 if align == 0 else 0.5 if align == 1 else 0.8)
                txt.setPos(xpos, y + 4)
                self.scene.addItem(txt)
        self.setSceneRect(0, 0, sum(cols), 22 + len(rows) * self.row_height)

    def update_footprint(self, rows):
        self._populate(rows)


class FootprintPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FootprintPanel")
        self._logger = logging.getLogger(__name__)
        self._agg = FootprintAggregator()
        self._pending_refresh = False
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(120)
        self._refresh_timer.timeout.connect(self._maybe_refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        header = QHBoxLayout()
        lbl = QLabel("Footprint Cluster")
        lbl.setFont(typography.inter(11, QFont.DemiBold))
        lbl.setStyleSheet(f"color:{colors.TEXT};")
        header.addWidget(lbl)
        header.addStretch()
        header.addWidget(self._legend("Imbalance ≥2x", colors.HIGHLIGHT))
        header.addWidget(self._legend("Absorption", colors.ACCENT_GREEN))
        layout.addLayout(header)

        self.view = FootprintView()
        layout.addWidget(self.view)
        QTimer.singleShot(0, self._wire_engine)
        self._refresh_timer.start()

    def _legend(self, text: str, color_hex: str) -> QWidget:
        bubble = QFrame()
        bubble.setFixedSize(10, 10)
        bubble.setStyleSheet(f"background:{color_hex}; border-radius:5px;")
        lbl = QLabel(text)
        lbl.setFont(typography.inter(10))
        lbl.setStyleSheet(f"color:{colors.MUTED};")
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.addWidget(bubble)
        h.addWidget(lbl)
        return container

    def _wire_engine(self, attempts: int = 0):
        window = self.window()
        engine = getattr(window, "data_engine", None) if window else None
        if engine:
            engine.trade.connect(self._on_trade)
            engine.candle_history.connect(self._on_candle_history)
            engine.candle_update.connect(self._on_candle_update)
            engine.timeframe_changed.connect(self._on_timeframe_changed)
            engine.symbol_changed.connect(self._on_symbol_changed)
        elif attempts < 6:
            QTimer.singleShot(150, lambda: self._wire_engine(attempts + 1))

    def _on_trade(self, evt: TradeEvent):
        self._agg.add_trade(evt.trade)
        self._pending_refresh = True

    def _on_candle_history(self, evt: CandleHistory):
        self._agg.add_candles(evt.candles)
        self._pending_refresh = True

    def _on_candle_update(self, evt: CandleUpdate):
        self._agg.add_candle_update(evt.candle, evt.closed)
        self._pending_refresh = True

    def _on_timeframe_changed(self, evt: TimeframeChanged):
        self._agg.set_timeframe(evt.timeframe)
        self._pending_refresh = True

    def _on_symbol_changed(self, evt: SymbolChanged):
        self._agg.set_symbol(evt.symbol)
        self._pending_refresh = True

    def _maybe_refresh(self):
        if not self._pending_refresh:
            return
        self._pending_refresh = False
        rows = self._agg.latest_cells(depth=30)
        self.view.update_footprint(rows)

    # Legacy hook
    def update_data(self, rows):
        pass
