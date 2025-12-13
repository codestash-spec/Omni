import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QPointF, Signal, QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSpinBox, QTabBar, QVBoxLayout, QWidget

from core.chart_engine import ChartEngine
from data_engine.models import Candle
from data_engine.utils import clamp_prices
from ui.theme import colors, typography


pg.setConfigOptions(background=colors.BACKGROUND, foreground=colors.TEXT, antialias=True, leftButtonPan=False)


@dataclass
class Candle:
    t: float
    open: float
    high: float
    low: float
    close: float
    volume: float


class TimeAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyle(tickTextOffset=3)
        self.setPen(pg.mkPen(colors.MUTED))
        self.setTickFont(typography.mono(9))

    def tickStrings(self, values, scale, spacing):
        return [datetime.utcfromtimestamp(v).strftime("%H:%M:%S") for v in values]


class PriceViewBox(pg.ViewBox):
    """
    Custom ViewBox to provide TradingView/MT5-like zoom & pan anchored to cursor.
    """

    def __init__(self, on_user_action=None, *args, **kwargs):
        super().__init__(*args, enableMenu=False, **kwargs)
        self.setMouseEnabled(x=True, y=True)
        self._on_user_action = on_user_action
        self.setLimits(minXRange=1, minYRange=0.0001)

    def wheelEvent(self, ev, axis=None):
        if ev.delta() == 0:
            return
        if self._on_user_action:
            self._on_user_action()
        # Zoom both axes with slight bias to horizontal
        zoom_in = ev.delta() > 0
        factor_x = 0.9 if zoom_in else 1 / 0.9
        factor_y = 0.95 if zoom_in else 1 / 0.95
        mouse_point = self.mapSceneToView(ev.scenePos())
        self._zoom_at(mouse_point, factor_x, factor_y)
        ev.accept()

    def _zoom_at(self, center, fx, fy):
        x0, x1 = self.state["viewRange"][0]
        y0, y1 = self.state["viewRange"][1]
        width = (x1 - x0) * fx
        height = (y1 - y0) * fy
        cx, cy = center.x(), center.y()
        self.setXRange(cx - width / 2, cx + width / 2, padding=0)
        self.setYRange(cy - height / 2, cy + height / 2, padding=0)

    def mouseDragEvent(self, ev, axis=None):
        if self._on_user_action:
            self._on_user_action()
        super().mouseDragEvent(ev, axis=axis)


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, candles: List[Candle]):
        super().__init__()
        self.candles = candles
        self.generatePicture()

    def generatePicture(self):
        self.picture = pg.QtGui.QPicture()
        painter = pg.QtGui.QPainter(self.picture)
        green = pg.mkColor(colors.ACCENT_GREEN)
        red = pg.mkColor(colors.ACCENT_RED)
        if not self.candles:
            painter.end()
            return
        # Dynamic body width based on median spacing
        xs = [c.t for c in self.candles]
        spacing = np.median(np.diff(xs)) if len(xs) > 1 else 1.0
        w = max(0.2, spacing * 0.35)
        for i, c in enumerate(self.candles):
            pen = pg.mkPen(green if c.close >= c.open else red)
            painter.setPen(pen)
            painter.drawLine(pg.QtCore.QPointF(c.t, c.low), pg.QtCore.QPointF(c.t, c.high))
            painter.setBrush(pg.mkBrush(pen.color()))
            rect = pg.QtCore.QRectF(c.t - w, min(c.open, c.close), w * 2, abs(c.close - c.open) or 0.001)
            painter.drawRect(rect)
        painter.end()

    def paint(self, painter, *args):
        painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return self.picture.boundingRect()

    def update_data(self, candles: List[Candle]):
        self.candles = candles
        self.generatePicture()
        self.update()


class ChartPanel(QWidget):
    timeframe_changed = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChartPanel")
        settings = QSettings("OmniFlow", "TerminalUI")
        self.bar_limit = int(settings.value("chart_max_bars", 500))
        self.engine = ChartEngine(max_candles=self.bar_limit)
        self._raw_candles: List[Candle] = []
        self._candles: List[Candle] = []
        self._logger = logging.getLogger(__name__)
        self._current_symbol = "N/A"
        self._follow_price = True
        self._last_view_width: Optional[float] = None
        self._candle_spacing = 60.0

        self.timeframes = ["1m", "5m", "15m", "1h", "4h", "1D"]
        self.timeframe_tabs = QTabBar()
        for i, tf in enumerate(self.timeframes):
            self.timeframe_tabs.addTab(tf)
            if tf == "1m":
                self.timeframe_tabs.setCurrentIndex(i)
        self.timeframe_tabs.setExpanding(False)
        self.timeframe_tabs.currentChanged.connect(self._on_timeframe_changed)

        self.price_label = QLabel("Price: -- | V: --")
        self.price_label.setFont(typography.mono(11, QFont.DemiBold))
        self.price_label.setStyleSheet(f"color: {colors.MUTED};")

        self.bar_spin = QSpinBox()
        self.bar_spin.setRange(300, 5000)
        self.bar_spin.setSingleStep(100)
        self.bar_spin.setValue(self.bar_limit)
        self.bar_spin.setSuffix(" bars")
        self.bar_spin.setFixedWidth(120)
        self.bar_spin.valueChanged.connect(self._on_bar_limit_changed)

        header = QHBoxLayout()
        title_label = QLabel("Price Chart")
        title_label.setFont(typography.inter(12, QFont.DemiBold))
        header.addWidget(title_label)
        header.addStretch()
        bar_lbl = QLabel("Bars:")
        bar_lbl.setFont(typography.inter(10, QFont.DemiBold))
        bar_lbl.setStyleSheet(f"color:{colors.MUTED};")
        header.addWidget(bar_lbl)
        header.addWidget(self.bar_spin)
        header.addWidget(self.timeframe_tabs)

        self.graphics = pg.GraphicsLayoutWidget()
        self.graphics.ci.layout.setSpacing(0)
        self.graphics.ci.layout.setContentsMargins(0, 0, 0, 0)

        self.price_axis = TimeAxisItem(orientation="bottom")
        self.volume_axis = TimeAxisItem(orientation="bottom")

        self.price_view = PriceViewBox(on_user_action=self._stop_follow)
        self.volume_view = PriceViewBox(on_user_action=self._stop_follow)
        self.volume_view.setMouseEnabled(x=True, y=False)
        self.price_view.sigRangeChangedManually.connect(self._stop_follow)
        self.volume_view.sigRangeChangedManually.connect(self._stop_follow)

        self.price_plot = self.graphics.addPlot(row=0, col=0, axisItems={"bottom": self.price_axis}, viewBox=self.price_view)
        self.price_plot.showGrid(x=False, y=False)
        self.price_plot.setMenuEnabled(False)
        self.price_plot.setLabel("left", "Price")
        self.price_plot.getAxis("left").setPen(pg.mkPen(colors.MUTED))
        self.price_plot.getAxis("bottom").setPen(pg.mkPen(colors.MUTED))

        self.volume_plot = self.graphics.addPlot(row=1, col=0, axisItems={"bottom": self.volume_axis}, viewBox=self.volume_view)
        self.volume_plot.setLabel("left", "Volume")
        self.volume_plot.showGrid(x=False, y=False)
        self.volume_plot.setMenuEnabled(False)
        self.volume_plot.setXLink(self.price_plot)
        self.graphics.ci.layout.setRowStretchFactor(0, 8)
        self.graphics.ci.layout.setRowStretchFactor(1, 2)

        self.candle_item = CandlestickItem([])
        self.candle_item.setZValue(3)
        self.price_plot.addItem(self.candle_item)

        self.ma_fast = pg.PlotDataItem(pen=pg.mkPen(colors.HIGHLIGHT, width=2))
        self.ma_slow = pg.PlotDataItem(pen=pg.mkPen(colors.ACCENT_BLUE, width=2))
        self.ma_fast.setZValue(2)
        self.ma_slow.setZValue(1)
        self.price_plot.addItem(self.ma_fast)
        self.price_plot.addItem(self.ma_slow)

        self.volume_bar = pg.BarGraphItem(x=[], height=[], width=0.6)
        self.volume_plot.addItem(self.volume_bar)

        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(colors.GRID, style=Qt.DashLine))
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(colors.GRID, style=Qt.DashLine))
        self.price_plot.addItem(self.v_line, ignoreBounds=True)
        self.price_plot.addItem(self.h_line, ignoreBounds=True)
        self.proxy = pg.SignalProxy(self.price_plot.scene().sigMouseMoved, rateLimit=60, slot=self._mouse_moved)
        self.crosshair_label = pg.TextItem(color=colors.TEXT, anchor=(0, 1))
        self.price_plot.addItem(self.crosshair_label, ignoreBounds=True)

        # Placeholder layers
        self.layer_bos_choch = pg.ItemGroup()
        self.layer_order_blocks = pg.ItemGroup()
        self.layer_fvg = pg.ItemGroup()
        self.layer_trades = pg.ItemGroup()
        self.layer_vwap_ma = pg.ItemGroup()
        for layer in (self.layer_bos_choch, self.layer_order_blocks, self.layer_fvg, self.layer_trades, self.layer_vwap_ma):
            self.price_plot.addItem(layer)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(header)
        layout.addWidget(self.graphics, stretch=1)
        layout.addWidget(self.price_label)

        self._raw_candles = []
        self._apply_bar_limit()

    def _generate_candles(self, n: int) -> List[Candle]:
        base = 42500
        candles = []
        last_close = base
        for i in range(n):
            change = random.uniform(-40, 40)
            open_p = last_close
            close_p = max(1, open_p + change)
            high = max(open_p, close_p) + random.uniform(5, 20)
            low = min(open_p, close_p) - random.uniform(5, 20)
            volume = random.randint(80, 320)
            candles.append(
                Candle(
                    open_time=i,
                    open=open_p,
                    high=high,
                    low=low,
                    close=close_p,
                    volume=volume,
                )
            )
            last_close = close_p
        return candles

    def _moving_average(self, data: np.ndarray, window: int) -> np.ndarray:
        if len(data) < window or window <= 1:
            return data
        return np.convolve(data, np.ones(window) / window, mode="same")

    def _mouse_moved(self, evt):
        pos = evt[0]
        if self.price_plot.sceneBoundingRect().contains(pos):
            mouse_point = self.price_view.mapSceneToView(pos)
            if self._candles:
                times = [c.t for c in self._candles]
                idx = np.searchsorted(times, mouse_point.x())
                idx = min(max(idx, 0), len(self._candles) - 1)
                candle = self._candles[idx]
                ts = datetime.utcfromtimestamp(candle.t).strftime("%H:%M:%S")
                self.price_label.setText(
                    f"{ts} | O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f} V:{candle.volume}"
                )
                self.crosshair_label.setText(
                    f"O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f} V:{candle.volume:.2f}"
                )
                self.crosshair_label.setPos(mouse_point.x(), mouse_point.y())
            self.v_line.setPos(mouse_point.x())
            self.h_line.setPos(mouse_point.y())

    def update_data(self, candles: List[Candle]):
        if not candles:
            return
        start = time.perf_counter()
        ordered = sorted(candles, key=lambda c: c.open_time)
        closes = np.array([c.close for c in ordered], dtype=float)
        filtered = ordered
        if closes.size:
            lower, upper = clamp_prices(closes, band=0.4)
            if lower is not None:
                filtered = [c for c in ordered if lower <= c.close <= upper and c.low > 0 and c.high > 0]
                dropped = len(ordered) - len(filtered)
                if dropped:
                    self._logger.warning(
                        "Dropped %d outlier candles for %s (clamp %.2f..%.2f)",
                        dropped,
                        ordered[0].symbol,
                        lower,
                        upper,
                    )
        self._raw_candles = filtered or ordered
        sym = ordered[0].symbol if ordered and hasattr(ordered[0], "symbol") else self._current_symbol or "N/A"
        if sym != self._current_symbol:
            self._current_symbol = sym
        if ordered:
            self._logger.info(
                "Chart update: %s candles=%d first=%.2f last=%.2f",
                self._current_symbol,
                len(self._raw_candles),
                ordered[0].close,
                ordered[-1].close,
            )
        self._apply_bar_limit()
        self._logger.info(
            "Chart applied bar limit=%d for %s in %.3fs",
            self.bar_limit,
            self._current_symbol,
            time.perf_counter() - start,
        )

    def _apply_bar_limit(self):
        source = self._raw_candles[-self.bar_limit :] if self._raw_candles else []
        self._candles = [
            Candle(t=c.open_time / 1000.0, open=c.open, high=c.high, low=c.low, close=c.close, volume=c.volume)
            for c in source
        ]
        self._candle_spacing = float(np.median(np.diff(np.array([c.t for c in self._candles]))) if len(self._candles) > 1 else 60.0)
        self.engine.set_history(
            [
                {
                    "time": c.open_time / 1000.0,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                }
                for c in source
            ]
        )
        self.candle_item.update_data(self._candles)
        closes = np.array([c.close for c in self._candles], dtype=float) if self._candles else np.array([])
        x_vals = [c.t for c in self._candles]
        self.ma_fast.setData(x_vals, closes if closes.size else [])
        self.ma_slow.setData(x_vals, self._moving_average(closes, 10) if closes.size else [])
        width = max(1.0, self._candle_spacing * 0.8)
        self.volume_bar.setOpts(
            x=x_vals,
            height=[c.volume for c in self._candles],
            width=width,
            brushes=[pg.mkBrush(colors.ACCENT_BLUE if c.close >= c.open else colors.ACCENT_RED) for c in self._candles],
        )
        self.price_plot.enableAutoRange(False)
        self.volume_plot.enableAutoRange(False)
        if self._candles:
            min_p = min(c.low for c in self._candles)
            max_p = max(c.high for c in self._candles)
            mid = self._candles[-1].close
            pad = max(1.0, (max_p - min_p) * 0.07)
            self.price_plot.setYRange(min_p - pad, max_p + pad, padding=0)
            vol_max = max(c.volume for c in self._candles)
            self.volume_plot.setYRange(0, vol_max * 1.2 if vol_max > 0 else 1, padding=0)
            last = self._candles[-1]
            self.price_label.setText(
                f"Price: {last.close:.2f} | O:{last.open:.2f} H:{last.high:.2f} L:{last.low:.2f} V:{last.volume:.2f}"
            )
            if self._follow_price:
                # Keep a trailing window while following
                view = self.price_plot.viewRange()
                x0, x1 = view[0]
                width_window = self._last_view_width or (x1 - x0)
                if not width_window or width_window <= 0:
                    width_window = max(self._candle_spacing * 120, 60.0)
                self._last_view_width = width_window
                self.price_plot.setXRange(last.t - width_window, last.t, padding=0)
                self.volume_plot.setXRange(last.t - width_window, last.t, padding=0)
        else:
            self.price_label.setText("Price: -- | V: --")

    def _on_bar_limit_changed(self, value: int):
        self.bar_limit = value
        self.engine.max_candles = value
        QSettings("OmniFlow", "TerminalUI").setValue("chart_max_bars", value)
        self._apply_bar_limit()

    def _on_timeframe_changed(self, idx: int):
        tf = self.timeframe_tabs.tabText(idx)
        self._logger.info("Chart timeframe changed -> %s", tf)
        self.timeframe_changed.emit(tf)

    def set_symbol(self, _symbol: str):
        self._raw_candles = []
        self._current_symbol = _symbol
        self._logger.info("Chart symbol changed -> %s; clearing local cache", _symbol)
        self._follow_price = True
        self._apply_bar_limit()

    def _stop_follow(self):
        self._follow_price = False

    def current_timeframe(self) -> str:
        idx = self.timeframe_tabs.currentIndex()
        return self.timeframe_tabs.tabText(idx) if idx >= 0 else "1m"

    def set_history(self, candles: List[Candle]):
        self._follow_price = True
        self.update_data(candles)

    def on_candle_update(self, candle: Candle, closed: bool):
        # Replace last candle or append if closed and new
        if closed:
            if self._raw_candles and candle.open_time <= self._raw_candles[-1].open_time:
                self._raw_candles[-1] = candle
            else:
                self._raw_candles.append(candle)
        else:
            if self._raw_candles:
                self._raw_candles[-1] = candle
            else:
                self._raw_candles.append(candle)
        self._apply_bar_limit()
