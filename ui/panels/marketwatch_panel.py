# ==========================================================
# IMPORTS STANDARD
# ==========================================================

import logging
import time

# ==========================================================
# IMPORTS QT
# ==========================================================

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# ==========================================================
# CORE STATE / MODELS
# ==========================================================

from core.app_state import AppState

# ✅ IMPORTANTÍSSIMO:
# Este painel renderiza rows do tipo TickerData vindos do CoreDataEngine/BinanceProvider.
# Sem este import, o painel pode falhar e nunca mostrar dados.
from core.data_engine.models import TickerData

# (Se quiseres manter por compatibilidade com imports anteriores, ok,
# mas Trade não é usado aqui e só adiciona ruído.)
# from core.data_engine.models import Trade

# ==========================================================
# UI THEME
# ==========================================================

from ui.theme import colors, typography


# ==========================================================
# MARKET WATCH PANEL
# ==========================================================

class MarketWatchPanel(QWidget):
    """
    Painel de Market Watch (lista de símbolos).

    Responsabilidades:
    - Mostrar preços, variação, volume e spread
    - Permitir seleção de símbolo
    - Sincronizar seleção com AppState
    """

    # Ordem fixa da watchlist (institucional / estável)
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

        # Nome do widget (docking / estilos)
        self.setObjectName("MarketWatchPanel")

        # Logger local
        self._logger = logging.getLogger(__name__)

        # Estado global da aplicação (injetado depois)
        self._app_state: AppState | None = None

        # Mapeamentos internos
        self._symbol_rows: dict[str, int] = {}     # símbolo -> linha
        self._row_symbol: dict[int, str] = {}      # linha -> símbolo

        # Flag para evitar loop infinito ao sincronizar seleção
        self._syncing_selection = False

        # Últimos dados recebidos por símbolo
        self._latest: dict[str, TickerData] = {}

        # ==================================================
        # LAYOUT PRINCIPAL
        # ==================================================

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ==================================================
        # TABELA
        # ==================================================

        self.table = QTableWidget(len(self.WATCHLIST_ORDER), 5)
        self.table.setHorizontalHeaderLabels(
            ["Symbol", "Last", "% Change", "Volume", "Spread"]
        )

        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Symbol
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Last
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # % Change
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Volume
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # Spread

        # Clique simples ou duplo muda o símbolo ativo
        self.table.cellClicked.connect(self._on_symbol_selected)
        self.table.cellDoubleClicked.connect(self._on_symbol_selected)

        layout.addWidget(self.table)

        # Render inicial (sem dados)
        self._render_static()

    # ======================================================
    # BIND AO APP STATE
    # ======================================================

    def bind_state(self, app_state: AppState):
        """
        Liga o MarketWatch ao AppState global.
        """
        self._app_state = app_state

        # Sempre que o símbolo mudar globalmente,
        # refletir na tabela
        self._app_state.symbol_changed.connect(
            self._reflect_symbol_selection
        )

    # ======================================================
    # UPDATE DE DADOS (TickerData)
    # ======================================================

    def update_data(self, rows):
        """
        Recebe dados de tickers do CoreDataEngine.

        rows: List[TickerData]
        """
        if rows is None:
            return

        start = time.perf_counter()

        # Atualiza cache interna apenas dos símbolos da watchlist
        for row in rows:
            sym = row.symbol.upper()
            if sym in self.WATCHLIST_ORDER:
                self._latest[sym] = row

        # Re-render
        self._render_static()

        self._logger.debug(
            "MarketWatch rendered %d symbols in %.3fs",
            len(self.WATCHLIST_ORDER),
            time.perf_counter() - start,
        )

        # Reforça seleção visual do símbolo ativo
        if self._app_state:
            self._reflect_symbol_selection(self._app_state.current_symbol)

    # ======================================================
    # RENDERIZAÇÃO
    # ======================================================

    def _render_static(self):
        """
        Renderiza a tabela com base nos dados mais recentes.
        """
        self.table.setRowCount(len(self.WATCHLIST_ORDER))
        self._symbol_rows.clear()
        self._row_symbol.clear()

        for r, sym in enumerate(self.WATCHLIST_ORDER):
            data = self._latest.get(sym)

            # Limpeza visual do símbolo
            display_sym = sym.replace("USDT", "") if sym.endswith("USDT") else sym
            display_sym = display_sym.replace("USDC", "USDC")

            symbol_item = QTableWidgetItem(display_sym)

            if data:
                last_item = QTableWidgetItem(f"{data.last_price:.4f}")
                change_item = QTableWidgetItem(f"{data.pct_change:+.2f}%")
                volume_item = QTableWidgetItem(f"{data.volume:.0f}")
                spread_item = QTableWidgetItem(f"{data.spread:.4f}")

                # Cor da variação
                change_item.setForeground(
                    QColor(
                        colors.ACCENT_GREEN
                        if data.pct_change >= 0
                        else colors.ACCENT_RED
                    )
                )
            else:
                last_item = QTableWidgetItem("--")
                change_item = QTableWidgetItem("--")
                volume_item = QTableWidgetItem("--")
                spread_item = QTableWidgetItem("--")

            # Estilo comum
            for item in [symbol_item, last_item, change_item, volume_item, spread_item]:
                item.setFont(typography.inter(10))
                item.setTextAlignment(Qt.AlignCenter)

            # Ajustes de alinhamento
            spread_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            volume_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            # Inserção na tabela
            self.table.setItem(r, 0, symbol_item)
            self.table.setItem(r, 1, last_item)
            self.table.setItem(r, 2, change_item)
            self.table.setItem(r, 3, volume_item)
            self.table.setItem(r, 4, spread_item)

            # Mapeamentos
            self._symbol_rows[sym] = r
            self._row_symbol[r] = sym

    # ======================================================
    # SELEÇÃO DE SÍMBOLO
    # ======================================================

    def _on_symbol_selected(self, row, _col):
        """
        Handler de clique na tabela.
        """
        if not self._app_state:
            return

        if self._syncing_selection:
            return

        symbol = self._row_symbol.get(row)
        if symbol:
            self._logger.info(
                "MarketWatch symbol selected -> %s (row=%d)",
                symbol,
                row,
            )
            self._app_state.set_symbol(symbol)

    def _reflect_symbol_selection(self, symbol: str | None):
        """
        Reflete no MarketWatch a seleção feita noutra parte da app.
        """
        if not symbol:
            return

        key = symbol.upper()
        if key not in self._symbol_rows:
            return

        row = self._symbol_rows[key]

        # Evita loop infinito (selectRow -> signal -> set_symbol)
        self._syncing_selection = True
        try:
            self.table.selectRow(row)
        finally:
            self._syncing_selection = False
