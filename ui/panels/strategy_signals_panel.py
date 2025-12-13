import random
import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.theme import colors, typography


class StrategySignalsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StrategySignalsPanel")
        self._logger = logging.getLogger(__name__)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(2000)
        self._refresh_timer.timeout.connect(self._refresh_dummy_signals)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        lbl = QLabel("Strategy Signals")
        lbl.setFont(typography.inter(11))
        header.addWidget(lbl)
        header.addStretch()
        self.pnl_label = QLabel("Total P&L: +$1245.50")
        self.pnl_label.setStyleSheet(f"color:{colors.ACCENT_GREEN};")
        self.win_label = QLabel("Win Rate: 68.5%")
        self.win_label.setStyleSheet(f"color:{colors.TEXT};")
        self.active_label = QLabel("Active Signals: 2")
        self.active_label.setStyleSheet(f"color:{colors.HIGHLIGHT};")
        for w in (self.pnl_label, self.win_label, self.active_label):
            w.setFont(typography.inter(10))
            header.addWidget(w)
        layout.addLayout(header)

        self.table = QTableWidget(4, 5)
        self.table.setHorizontalHeaderLabels(["Time", "Type", "Strategy", "Price", "Strength"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        # autosize first columns to contents
        header_widget = self.table.horizontalHeader()
        for idx in range(self.table.columnCount() - 1):
            header_widget.setSectionResizeMode(idx, QHeaderView.ResizeToContents)
        header_widget.setSectionResizeMode(self.table.columnCount() - 1, QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.populate(self._dummy_rows())
        self._wire_engine()
        self._refresh_timer.start()

    def _dummy_rows(self):
        strategies = ["Mean Reversion", "Momentum", "Volume Spike", "Breakout"]
        rows = []
        for i in range(4):
            rows.append(
                {
                    "time": f"03:{10+i:02d} PM",
                    "type": random.choice(["Long", "Short"]),
                    "strategy": strategies[i % len(strategies)],
                    "price": round(42380 + random.uniform(-50, 120), 2),
                    "strength": random.randint(60, 98),
                }
            )
        return rows

    def _refresh_dummy_signals(self):
        """Update dummy signals periodically."""
        self.populate(self._dummy_rows())

    def _wire_engine(self, attempts=0):
        """Hook to CoreDataEngine when ready."""
        window = self.window()
        engine = getattr(window, "data_engine", None) if window else None
        if engine:
            try:
                engine.candle_update.connect(self._on_candle)
                self._logger.info("StrategySignalsPanel wired to CoreDataEngine")
            except Exception as e:
                self._logger.warning("StrategySignalsPanel wire failed: %s", e)
        elif attempts < 3:
            QTimer.singleShot(200, lambda: self._wire_engine(attempts + 1))

    def _on_candle(self, evt):
        """Will process real candle data for signal generation."""
        pass

    def populate(self, rows):
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            time_item = QTableWidgetItem(row["time"])
            type_item = QTableWidgetItem(row["type"])
            strat_item = QTableWidgetItem(row["strategy"])
            price_item = QTableWidgetItem(f"{row['price']:.2f}")
            for item in [time_item, type_item, strat_item, price_item]:
                item.setFont(typography.inter(10))
                item.setTextAlignment(Qt.AlignCenter)
            type_item.setForeground(QColor(colors.ACCENT_GREEN if row["type"] == "Long" else colors.ACCENT_RED))
            price_item.setForeground(QColor(colors.TEXT))
            self.table.setItem(r, 0, time_item)
            self.table.setItem(r, 1, type_item)
            self.table.setItem(r, 2, strat_item)
            self.table.setItem(r, 3, price_item)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(row["strength"])
            bar.setTextVisible(True)
            bar.setFormat(f"{row['strength']}%")
            bar.setStyleSheet(
                f"""
            QProgressBar::chunk {{
                background: {colors.ACCENT_GREEN if row['type']=='Long' else colors.ACCENT_RED};
            }}
            """
            )
            self.table.setCellWidget(r, 4, bar)

    def update_data(self, rows):
        self.populate(rows)
