import logging
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from core.app_state import AppState
from core.data_engine.models import Trade

from ui.theme import colors, typography


class MarketWatchPanel(QWidget):
    WATCHLIST_ORDER = [
        "BTCUSDT",
        "ETHUSDT",
        "USDTUSDC",
        "XRPUSDT",
        "BNBUSDT",
        "USDCUSDT",
        "SOLUSDT",
        "TRXUSDT",
        "DOGEUSDT",
        "ADAUSDT",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MarketWatchPanel")
        self._logger = logging.getLogger(__name__)
        self._app_state: AppState | None = None
        self._symbol_rows: dict[str, int] = {}
        self._syncing_selection = False
        self._latest: dict[str, TickerData] = {}
        self._row_symbol: dict[int, str] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.table = QTableWidget(len(self.WATCHLIST_ORDER), 5)
        self.table.setHorizontalHeaderLabels(["Symbol", "Last", "% Change", "Volume", "Spread"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.cellClicked.connect(self._on_symbol_selected)
        self.table.cellDoubleClicked.connect(self._on_symbol_selected)
        layout.addWidget(self.table)

        self._render_static()

    def bind_state(self, app_state: AppState):
        self._app_state = app_state
        self._app_state.symbol_changed.connect(self._reflect_symbol_selection)

    def update_data(self, rows):
        # rows: List[TickerData]
        if rows is None:
            return
        start = time.perf_counter()
        for row in rows:
            sym = row.symbol.upper()
            if sym in self.WATCHLIST_ORDER:
                self._latest[sym] = row

        self._render_static()
        self._logger.debug(
            "MarketWatch rendered %d symbols in %.3fs",
            len(self.WATCHLIST_ORDER),
            time.perf_counter() - start,
        )
        self._reflect_symbol_selection(self._app_state.current_symbol if self._app_state else None)

    def _render_static(self):
        self.table.setRowCount(len(self.WATCHLIST_ORDER))
        self._symbol_rows.clear()
        for r, sym in enumerate(self.WATCHLIST_ORDER):
            data = self._latest.get(sym)
            display_sym = sym.replace("USDT", "") if sym.endswith("USDT") else sym
            display_sym = display_sym.replace("USDC", "USDC")

            symbol_item = QTableWidgetItem(display_sym)

            if data:
                last_item = QTableWidgetItem(f"{data.last_price:.4f}")
                change_item = QTableWidgetItem(f"{data.pct_change:+.2f}%")
                volume_item = QTableWidgetItem(f"{data.volume:.0f}")
                spread_item = QTableWidgetItem(f"{data.spread:.4f}")
                change_item.setForeground(QColor(colors.ACCENT_GREEN if data.pct_change >= 0 else colors.ACCENT_RED))
            else:
                last_item = QTableWidgetItem("--")
                change_item = QTableWidgetItem("--")
                volume_item = QTableWidgetItem("--")
                spread_item = QTableWidgetItem("--")

            for item in [symbol_item, last_item, change_item, volume_item, spread_item]:
                item.setFont(typography.inter(10))
                item.setTextAlignment(Qt.AlignCenter)
            spread_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            volume_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self.table.setItem(r, 0, symbol_item)
            self.table.setItem(r, 1, last_item)
            self.table.setItem(r, 2, change_item)
            self.table.setItem(r, 3, volume_item)
            self.table.setItem(r, 4, spread_item)
            self._symbol_rows[sym] = r
            self._row_symbol[r] = sym

    def _on_symbol_selected(self, row, _col):
        if not self._app_state:
            return
        if self._syncing_selection:
            return
        symbol = self._row_symbol.get(row)
        if symbol:
            self._logger.info("MarketWatch symbol selected -> %s (row=%d)", symbol, row)
            self._app_state.set_symbol(symbol)

    def _reflect_symbol_selection(self, symbol: str | None):
        if not symbol:
            return
        key = symbol.upper()
        if key not in self._symbol_rows:
            return
        row = self._symbol_rows[key]
        self._syncing_selection = True
        try:
            self.table.selectRow(row)
        finally:
            self._syncing_selection = False
