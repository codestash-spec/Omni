# ==========================================================
# IMPORTS
# ==========================================================

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import numpy as np
import pyqtgraph as pg

from PySide6.QtCore import Qt, QPointF, Signal, QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

# Core engines
from core.chart_engine import ChartEngine
from core.data_engine.models import Candle
from core.data_engine.utils import clamp_prices

# UI theme
from ui.theme import colors, typography


# ==========================================================
# PYQTGRAPH GLOBAL CONFIG
# ==========================================================

pg.setConfigOptions(
    background=colors.BACKGROUND,
    foreground=colors.TEXT,
    antialias=True,
    leftButtonPan=False,
)


# ==========================================================
# INTERNAL CANDLE STRUCT (RENDER-FRIENDLY)
# ==========================================================

@dataclass
class Candle:
    """
    Candle normalizada para renderização:
    - t → timestamp em segundos
    - open/high/low/close
    - volume
    """
    t: float
    open: float
    high: float
    low: float
    close: float
    volume: float


# ==========================================================
# CUSTOM TIME AXIS
# ==========================================================

class TimeAxisItem(pg.AxisItem):
    """
    Axis temporal customizado (UTC),
    estilo TradingView / MT5.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyle(tickTextOffset=3)
        self.setPen(pg.mkPen(colors.MUTED))
        self.setTickFont(typography.mono(9))

    def tickStrings(self, values, scale, spacing):
        return [
            datetime.utcfromtimestamp(v).strftime("%H:%M:%S")
            for v in values
        ]


# ==========================================================
# CUSTOM VIEWBOX — ZOOM & PAN PROFISSIONAL
# ==========================================================

class PriceViewBox(pg.ViewBox):
    """
    ViewBox customizada:
    - Zoom centrado no cursor
    - Pan suave
    - Detecção de interação do utilizador
    """

    def __init__(self, on_user_action=None, *args, **kwargs):
        super().__init__(*args, enableMenu=False, **kwargs)
        self.setMouseEnabled(x=True, y=True)
        self._on_user_action = on_user_action
        self.setLimits(minXRange=1, minYRange=0.0001)

    def wheelEvent(self, ev, axis=None):
        """
        Zoom com rato:
        - Horizontal dominante
        - Ancora no cursor
        """
        if ev.delta() == 0:
            return

        if self._on_user_action:
            self._on_user_action()

        zoom_in = ev.delta() > 0
        factor_x = 0.9 if zoom_in else 1 / 0.9
        factor_y = 0.95 if zoom_in else 1 / 0.95

        mouse_point = self.mapSceneToView(ev.scenePos())
        self._zoom_at(mouse_point, factor_x, factor_y)
        ev.accept()

    def _zoom_at(self, center, fx, fy):
        """
        Zoom matematicamente centrado num ponto.
        """
        x0, x1 = self.state["viewRange"][0]
        y0, y1 = self.state["viewRange"][1]

        width = (x1 - x0) * fx
        height = (y1 - y0) * fy

        cx, cy = center.x(), center.y()
        self.setXRange(cx - width / 2, cx + width / 2, padding=0)
        self.setYRange(cy - height / 2, cy + height / 2, padding=0)

    def mouseDragEvent(self, ev, axis=None):
        """
        Pan manual → desativa follow-price.
        """
        if self._on_user_action:
            self._on_user_action()
        super().mouseDragEvent(ev, axis=axis)


# ==========================================================
# CANDLESTICK ITEM — RENDER DE ALTA PERFORMANCE
# ==========================================================

class CandlestickItem(pg.GraphicsObject):
    """
    Renderização manual de candles:
    - Muito mais rápida que PlotDataItem
    - Corpo e wick desenhados com QPainter
    """

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

        # Largura dinâmica baseada no espaçamento real
        xs = [c.t for c in self.candles]
        spacing = np.median(np.diff(xs)) if len(xs) > 1 else 1.0
        w = max(0.2, spacing * 0.35)

        for c in self.candles:
            pen = pg.mkPen(green if c.close >= c.open else red)
            painter.setPen(pen)

            # Wick
            painter.drawLine(
                QPointF(c.t, c.low),
                QPointF(c.t, c.high),
            )

            # Body
            painter.setBrush(pg.mkBrush(pen.color()))
            rect = pg.QtCore.QRectF(
                c.t - w,
                min(c.open, c.close),
                w * 2,
                abs(c.close - c.open) or 0.001,
            )
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


# ==========================================================
# MAIN CHART PANEL
# ==========================================================

class ChartPanel(QWidget):
    """
    Painel principal de gráfico:
    - Candles
    - Volume
    - Médias móveis
    - Crosshair
    - Follow price
    """

    timeframe_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChartPanel")

        # --------------------------
        # SETTINGS / ENGINE
        # --------------------------

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

        # --------------------------
        # TIMEFRAMES
        # --------------------------

        self.timeframes = ["1m", "5m", "15m", "1h", "4h", "1D"]
        self.timeframe_tabs = QTabBar()

        for i, tf in enumerate(self.timeframes):
            self.timeframe_tabs.addTab(tf)
            if tf == "1m":
                self.timeframe_tabs.setCurrentIndex(i)

        self.timeframe_tabs.setExpanding(False)
        self.timeframe_tabs.currentChanged.connect(self._on_timeframe_changed)

        # --------------------------
        # HEADER UI
        # --------------------------

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

        # --------------------------
        # GRAPHICS LAYOUT
        # --------------------------

        self.graphics = pg.GraphicsLayoutWidget()
        self.graphics.ci.layout.setSpacing(0)
        self.graphics.ci.layout.setContentsMargins(0, 0, 0, 0)

        self.price_axis = TimeAxisItem(orientation="bottom")
        self.volume_axis = TimeAxisItem(orientation="bottom")

        self.price_view = PriceViewBox(on_user_action=self._stop_follow)
        self.volume_view = PriceViewBox(on_user_action=self._stop_follow)
        self.volume_view.setMouseEnabled(x=True, y=False)

        # --------------------------
        # PRICE PLOT
        # --------------------------

        self.price_plot = self.graphics.addPlot(
            row=0,
            col=0,
            axisItems={"bottom": self.price_axis},
            viewBox=self.price_view,
        )

        self.price_plot.setMenuEnabled(False)
        self.price_plot.setLabel("left", "Price")
        self.price_plot.getAxis("left").setPen(pg.mkPen(colors.MUTED))
        self.price_plot.getAxis("bottom").setPen(pg.mkPen(colors.MUTED))

        # --------------------------
        # VOLUME PLOT
        # --------------------------

        self.volume_plot = self.graphics.addPlot(
            row=1,
            col=0,
            axisItems={"bottom": self.volume_axis},
            viewBox=self.volume_view,
        )

        self.volume_plot.setLabel("left", "Volume")
        self.volume_plot.setMenuEnabled(False)
        self.volume_plot.setXLink(self.price_plot)

        self.graphics.ci.layout.setRowStretchFactor(0, 8)
        self.graphics.ci.layout.setRowStretchFactor(1, 2)

        # --------------------------
        # ITEMS
        # --------------------------

        self.candle_item = CandlestickItem([])
        self.price_plot.addItem(self.candle_item)

        self.ma_fast = pg.PlotDataItem(pen=pg.mkPen(colors.HIGHLIGHT, width=2))
        self.ma_slow = pg.PlotDataItem(pen=pg.mkPen(colors.ACCENT_BLUE, width=2))
        self.price_plot.addItem(self.ma_fast)
        self.price_plot.addItem(self.ma_slow)

        self.volume_bar = pg.BarGraphItem(x=[], height=[], width=0.6)
        self.volume_plot.addItem(self.volume_bar)

        # --------------------------
        # CROSSHAIR
        # --------------------------

        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(colors.GRID, style=Qt.DashLine))
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(colors.GRID, style=Qt.DashLine))

        self.price_plot.addItem(self.v_line, ignoreBounds=True)
        self.price_plot.addItem(self.h_line, ignoreBounds=True)

        self.crosshair_label = pg.TextItem(color=colors.TEXT, anchor=(0, 1))
        self.price_plot.addItem(self.crosshair_label, ignoreBounds=True)

        self.proxy = pg.SignalProxy(
            self.price_plot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self._mouse_moved,
        )

        # --------------------------
        # LAYOUT FINAL
        # --------------------------

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.graphics, stretch=1)
        layout.addWidget(self.price_label)

        self._apply_bar_limit()

    # ==========================================================
    # DATA UPDATE
    # ==========================================================

    def update_data(self, candles: List[Candle]):
        """
        Recebe candles do DataEngine.
        """
        if not candles:
            return

        ordered = sorted(candles, key=lambda c: c.open_time)

        closes = np.array([c.close for c in ordered], dtype=float)
        filtered = ordered

        # Outlier clamp
        if closes.size:
            lower, upper = clamp_prices(closes, band=0.4)
            if lower is not None:
                filtered = [
                    c for c in ordered
                    if lower <= c.close <= upper
                    and c.low > 0
                    and c.high > 0
                ]

        self._raw_candles = filtered or ordered
        self._apply_bar_limit()

    # ==========================================================
    # APPLY BAR LIMIT + RENDER
    # ==========================================================

    def _apply_bar_limit(self):
        """
        Aplica limite de candles e renderiza tudo.
        """
        source = self._raw_candles[-self.bar_limit :] if self._raw_candles else []

        self._candles = [
            Candle(
                t=c.open_time / 1000.0,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for c in source
        ]

        self.candle_item.update_data(self._candles)

        # Médias móveis
        closes = np.array([c.close for c in self._candles], dtype=float)
        x_vals = [c.t for c in self._candles]

        self.ma_fast.setData(x_vals, closes if closes.size else [])
        self.ma_slow.setData(x_vals, np.convolve(closes, np.ones(10)/10, mode="same") if closes.size else [])

        # Volume
        self.volume_bar.setOpts(
            x=x_vals,
            height=[c.volume for c in self._candles],
            width=max(1.0, self._candle_spacing * 0.8),
            brushes=[
                pg.mkBrush(colors.ACCENT_GREEN if c.close >= c.open else colors.ACCENT_RED)
                for c in self._candles
            ],
        )

        # Follow price
        if self._candles and self._follow_price:
            last = self._candles[-1]
            width = self._last_view_width or max(self._candle_spacing * 120, 60)
            self.price_plot.setXRange(last.t - width, last.t, padding=0)
            self.volume_plot.setXRange(last.t - width, last.t, padding=0)

    # ==========================================================
    # INTERACTIONS
    # ==========================================================

    def _mouse_moved(self, evt):
        pos = evt[0]
        if self.price_plot.sceneBoundingRect().contains(pos):
            mouse_point = self.price_view.mapSceneToView(pos)
            self.v_line.setPos(mouse_point.x())
            self.h_line.setPos(mouse_point.y())

    def _stop_follow(self):
        self._follow_price = False

    def _on_bar_limit_changed(self, value: int):
        self.bar_limit = value
        QSettings("OmniFlow", "TerminalUI").setValue("chart_max_bars", value)
        self._apply_bar_limit()

    def _on_timeframe_changed(self, idx: int):
        tf = self.timeframe_tabs.tabText(idx)
        self.timeframe_changed.emit(tf)

    def current_timeframe(self) -> str:
        idx = self.timeframe_tabs.currentIndex()
        return self.timeframe_tabs.tabText(idx) if idx >= 0 else "1m"
