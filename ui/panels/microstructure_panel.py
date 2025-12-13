import random
import logging

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ui.theme import colors, typography
from core.data_engine.events import TradeEvent, CandleUpdate


class MicrostructurePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MicrostructurePanel")
        self._logger = logging.getLogger(__name__)
        self._cum_delta = 0.0
        self._ofi = 0.0
        self._vpin = 50
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(500)
        self._refresh_timer.timeout.connect(self._refresh_dummy_data)

        header = QHBoxLayout()
        lbl = QLabel("Microstructure")
        lbl.setFont(typography.inter(11))
        header.addWidget(lbl)
        header.addStretch()
        self.regime = QLabel("Regime: TRENDING")
        self.regime.setStyleSheet(f"color:{colors.ACCENT_GREEN};")
        header.addWidget(self.regime)

        self.cum_delta_plot = pg.PlotWidget()
        self.cum_delta_plot.showGrid(x=True, y=True, alpha=0.2)
        self.cum_delta_plot.setLabel("left", "Cumulative Delta")
        self.cum_delta_plot.getPlotItem().hideButtons()

        self.ofi_plot = pg.PlotWidget()
        self.ofi_plot.showGrid(x=True, y=True, alpha=0.2)
        self.ofi_plot.setLabel("left", "Order Flow Imbalance (OFI)")
        self.ofi_plot.getPlotItem().hideButtons()

        self.vpin = QProgressBar()
        self.vpin.setRange(0, 100)
        self.vpin.setValue(49)
        self.vpin.setFormat("VPIN (Volume-Synchronized Probability of Informed Trading) %p%")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self.cum_delta_plot, stretch=1)
        layout.addWidget(self.ofi_plot, stretch=1)
        layout.addWidget(self.vpin)

        self._populate()
        self._wire_engine()
        self._refresh_timer.start()

    def _populate(self):
        x = np.arange(80)
        cum_delta = np.cumsum(np.random.normal(0, 3, size=len(x)))
        ofi = np.cumsum(np.random.normal(0, 2, size=len(x)))
        self.cum_delta_plot.plot(x, cum_delta, pen=pg.mkPen(colors.ACCENT_BLUE, width=2))
        self.ofi_plot.plot(x, ofi, pen=pg.mkPen(colors.ACCENT_GREEN, width=2))

    def _refresh_dummy_data(self):
        """Update dummy data for now; will be replaced with real engine data."""
        self._cum_delta += np.random.normal(0, 3)
        self._ofi += np.random.normal(0, 2)
        self._vpin = max(0, min(100, self._vpin + np.random.uniform(-5, 5)))
        self.vpin.setValue(int(self._vpin))

    def _wire_engine(self, attempts=0):
        """Hook to CoreDataEngine when ready."""
        window = self.window()
        engine = getattr(window, "data_engine", None) if window else None
        if engine:
            try:
                engine.trade.connect(self._on_trade)
                engine.candle_update.connect(self._on_candle_update)
                self._logger.info("MicrostructurePanel wired to CoreDataEngine")
            except Exception as e:
                self._logger.warning("MicrostructurePanel wire failed: %s", e)
        elif attempts < 3:
            QTimer.singleShot(200, lambda: self._wire_engine(attempts + 1))

    def _on_trade(self, evt: TradeEvent):
        """Real trade data will update delta calculations."""
        pass

    def _on_candle_update(self, evt: CandleUpdate):
        """Real candle data will update OFI."""
        pass

    def update_data(self, micro_data):
        self.cum_delta_plot.clear()
        self.ofi_plot.clear()
        self._populate()
