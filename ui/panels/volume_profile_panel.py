import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Tuple, Optional

from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QTimer, Qt

from core.data_engine.events import TradeEvent, CandleHistory, CandleUpdate, TimeframeChanged, SymbolChanged
from data_engine.models import Trade, Candle
from ui.theme import colors, typography


@dataclass
class ProfileBucket:
    price: float
    volume: float


class VolumeProfileAggregator:
    def __init__(self):
        self.trades: Deque[Trade] = deque(maxlen=8000)
        self.candles: List[Candle] = []
        self.timeframe_ms = 60_000
        self.symbol = "BTCUSDT"
        self.window_candles = 120

    def set_symbol(self, symbol: str):
        self.symbol = symbol.upper()
        self.trades.clear()
        self.candles.clear()

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
        self.trades.clear()
        self.candles.clear()

    def add_candles(self, candles: List[Candle]):
        self.candles = list(candles)[-self.window_candles :]

    def add_candle_update(self, candle: Candle, closed: bool):
        if not closed:
            return
        self.candles.append(candle)
        self.candles = self.candles[-self.window_candles :]

    def add_trade(self, trade: Trade):
        if trade.symbol.upper() != self.symbol:
            return
        self.trades.append(trade)

    def _window_start_ms(self) -> Optional[int]:
        if not self.candles:
            return None
        return self.candles[-1].open_time - self.timeframe_ms * (self.window_candles - 1)

    def profile(self) -> Tuple[List[ProfileBucket], Optional[float], Optional[float], Optional[float]]:
        start_ms = self._window_start_ms()
        buckets: Dict[float, float] = defaultdict(float)
        if start_ms is not None:
            cutoff = start_ms
            while self.trades and self.trades[0].ts < cutoff:
                self.trades.popleft()
        for t in self.trades:
            price = round(t.price, 2)
            buckets[price] += t.qty
        if not buckets and self.candles:
            # fallback: use candle volumes at close price
            for c in self.candles:
                buckets[round(c.close, 2)] += c.volume
        items = [ProfileBucket(price=p, volume=v) for p, v in buckets.items() if v > 1e-6]
        if not items:
            return [], None, None, None
        items.sort(key=lambda b: b.price)
        total_vol = sum(b.volume for b in items)
        poc_price = max(items, key=lambda b: b.volume).price if items else None

        # Value Area 70% around POC
        sorted_by_vol = sorted(items, key=lambda b: b.volume, reverse=True)
        acc = 0.0
        selected_prices = set()
        for b in sorted_by_vol:
            acc += b.volume
            selected_prices.add(b.price)
            if acc >= total_vol * 0.7:
                break
        vah = max(selected_prices) if selected_prices else None
        val = min(selected_prices) if selected_prices else None
        # limit to top 80 levels by volume to avoid huge scrolls
        limited = sorted_by_vol[:80]
        limited.sort(key=lambda b: b.price, reverse=True)
        return limited, poc_price, vah, val


class VolumeProfileView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.row_height = 22

    def populate(self, buckets: List[ProfileBucket], poc: Optional[float], vah: Optional[float], val: Optional[float]):
        self.scene.clear()
        max_vol = max(b.volume for b in buckets) if buckets else 1
        width_max = 220
        x_origin = 80
        font = typography.mono(10)
        buckets_sorted = sorted(buckets, key=lambda b: b.price, reverse=True)
        for i, bucket in enumerate(buckets_sorted):
            y = i * self.row_height
            bar_width = width_max * bucket.volume / max_vol if max_vol else 0
            color = colors.ACCENT_BLUE
            if poc is not None and abs(bucket.price - poc) < 1e-6:
                color = colors.HIGHLIGHT
            elif val is not None and vah is not None and val <= bucket.price <= vah:
                color = colors.ACCENT_BLUE
            rect = QGraphicsRectItem(x_origin, y + 4, bar_width, self.row_height - 8)
            rect.setBrush(QColor(color).darker(130))
            rect.setPen(QColor(colors.BACKGROUND))
            self.scene.addItem(rect)

            price_txt = QGraphicsTextItem(f"{bucket.price:.2f}")
            price_txt.setFont(font)
            price_txt.setDefaultTextColor(QColor(colors.MUTED))
            price_txt.setPos(0, y + 2)
            self.scene.addItem(price_txt)

            vol_txt = QGraphicsTextItem(f"{bucket.volume:.2f}")
            vol_txt.setFont(font)
            vol_txt.setDefaultTextColor(QColor(colors.TEXT))
            vol_txt.setPos(x_origin + bar_width + 6, y + 2)
            self.scene.addItem(vol_txt)

        self.setSceneRect(0, 0, x_origin + width_max + 80, len(buckets_sorted) * self.row_height)

    def update_profile(self, buckets, poc, vah, val):
        self.populate(buckets, poc, vah, val)


class VolumeProfilePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VolumeProfilePanel")
        self._logger = logging.getLogger(__name__)
        self._agg = VolumeProfileAggregator()
        self._pending = False
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(200)
        self._refresh_timer.timeout.connect(self._refresh_if_needed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        lbl = QLabel("Volume Profile")
        lbl.setFont(typography.inter(11, QFont.DemiBold))
        header.addWidget(lbl)
        header.addStretch()
        header.addWidget(self._legend("POC (Point of Control)", colors.HIGHLIGHT))
        header.addWidget(self._legend("Value Area (70%)", colors.ACCENT_BLUE))
        layout.addLayout(header)

        self.view = VolumeProfileView()
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
            try:
                if not hasattr(engine, 'trade') or not hasattr(engine, 'candle_history'):
                    self._logger.warning("CoreDataEngine missing required signals; retrying...")
                    if attempts < 6:
                        QTimer.singleShot(150, lambda: self._wire_engine(attempts + 1))
                    return
                engine.trade.connect(self._on_trade)
                engine.candle_history.connect(self._on_candle_history)
                engine.candle_update.connect(self._on_candle_update)
                engine.timeframe_changed.connect(self._on_timeframe_changed)
                engine.symbol_changed.connect(self._on_symbol_changed)
                self._logger.info("VolumeProfilePanel wired to CoreDataEngine successfully")
            except Exception as e:
                self._logger.error("Failed to wire VolumeProfilePanel: %s", e)
                if attempts < 6:
                    QTimer.singleShot(150, lambda: self._wire_engine(attempts + 1))
        elif attempts < 6:
            QTimer.singleShot(150, lambda: self._wire_engine(attempts + 1))

    def _on_trade(self, evt: TradeEvent):
        self._agg.add_trade(evt.trade)
        self._pending = True

    def _on_candle_history(self, evt: CandleHistory):
        self._agg.add_candles(evt.candles)
        self._pending = True

    def _on_candle_update(self, evt: CandleUpdate):
        self._agg.add_candle_update(evt.candle, evt.closed)
        self._pending = True

    def _on_timeframe_changed(self, evt: TimeframeChanged):
        self._agg.set_timeframe(evt.timeframe)
        self._pending = True

    def _on_symbol_changed(self, evt: SymbolChanged):
        self._agg.set_symbol(evt.symbol)
        self._pending = True

    def _refresh_if_needed(self):
        if not self._pending:
            return
        self._pending = False
        buckets, poc, vah, val = self._agg.profile()
        self.view.update_profile(buckets, poc, vah, val)

    # legacy hook
    def update_data(self, rows):
        pass
