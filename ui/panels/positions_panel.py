# ==========================================================
# IMPORTS BASE
# ==========================================================

import logging


# ==========================================================
# IMPORTS QT
# ==========================================================

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)


# ==========================================================
# TEMA DA UI
# ==========================================================

from ui.theme import colors, typography


# ==========================================================
# POSITIONS PANEL
# ==========================================================

class PositionsPanel(QWidget):
    """
    Painel de posições abertas.

    Atualmente:
    - dados fictícios (dummy)
    - atualização automática para simular P&L
    - botões de ação (Close / Reduce / Add) apenas visuais

    Futuro:
    - integração com CoreDataEngine / Execution Engine
    - ações reais (close parcial, add, reduce)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("PositionsPanel")
        self._logger = logging.getLogger(__name__)


        # ==================================================
        # TIMER DE REFRESH (DUMMY)
        # ==================================================

        # Atualiza posições a cada 1 segundo
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self._refresh_dummy_positions)


        # ==================================================
        # LAYOUT PRINCIPAL
        # ==================================================

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)


        # ==================================================
        # TABELA DE POSIÇÕES
        # ==================================================

        self.table = QTableWidget(3, 7)
        self.table.setHorizontalHeaderLabels(
            ["Symbol", "Side", "Entry", "Current", "P&L", "%", "Action"]
        )

        # Configuração visual da tabela
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)

        # Permitir edição por clique (placeholder)
        self.table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.SelectedClicked
        )

        header = self.table.horizontalHeader()

        # Auto-size das colunas (exceto a última)
        for idx in range(self.table.columnCount() - 1):
            header.setSectionResizeMode(idx, QHeaderView.ResizeToContents)

        # Última coluna ocupa o espaço restante (botões)
        header.setSectionResizeMode(
            self.table.columnCount() - 1,
            QHeaderView.Stretch,
        )

        layout.addWidget(self.table)


        # ==================================================
        # BARRA DE RESUMO (SUMMARY BAR)
        # ==================================================

        self.summary_bar = self._build_summary_bar()
        layout.addWidget(self.summary_bar)


        # ==================================================
        # DADOS INICIAIS (DUMMY)
        # ==================================================

        self.populate(self._dummy_rows())

        # Tentar ligar ao CoreDataEngine
        self._wire_engine()

        # Iniciar refresh dummy
        self._refresh_timer.start()


    # ======================================================
    # DADOS FICTÍCIOS
    # ======================================================

    def _dummy_rows(self):
        """
        Retorna posições fictícias para UI / testes.
        """
        return [
            {"symbol": "BTC/USD", "side": "Long", "entry": 41500.0, "current": 42500.5, "pl": 500.25},
            {"symbol": "ES", "side": "Short", "entry": 4725.5, "current": 4750.25, "pl": -49.5},
            {"symbol": "GC", "side": "Long", "entry": 2038.2, "current": 2045.7, "pl": 74.0},
        ]


    def _refresh_dummy_positions(self):
        """
        Atualiza posições fictícias simulando variações de preço e P&L.
        """
        import random

        rows = self._dummy_rows()

        for i in range(len(rows)):
            rows[i]["current"] += random.uniform(-1, 1)
            rows[i]["pl"] += random.uniform(-10, 10)

        self.populate(rows)


    # ======================================================
    # LIGAÇÃO AO CORE DATA ENGINE
    # ======================================================

    def _wire_engine(self, attempts=0):
        """
        Liga ao CoreDataEngine quando disponível.

        Futuro:
        - receber eventos reais de trades
        - atualizar posições abertas
        """
        window = self.window()
        engine = getattr(window, "data_engine", None) if window else None

        if engine:
            try:
                engine.trade.connect(self._on_trade)
                self._logger.info("PositionsPanel wired to CoreDataEngine")
            except Exception as e:
                self._logger.warning(
                    "PositionsPanel wire failed: %s", e
                )
        elif attempts < 3:
            QTimer.singleShot(
                200,
                lambda: self._wire_engine(attempts + 1),
            )


    def _on_trade(self, evt):
        """
        Futuro:
        - atualizar posições com dados reais
        """
        pass


    # ======================================================
    # RENDERIZAÇÃO DA TABELA
    # ======================================================

    def populate(self, rows):
        """
        Renderiza posições na tabela.
        """
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            # Itens básicos
            symbol_item = QTableWidgetItem(row["symbol"])
            side_item = QTableWidgetItem(row["side"])
            entry_item = QTableWidgetItem(f"{row['entry']:.2f}")
            current_item = QTableWidgetItem(f"{row['current']:.2f}")
            pl_item = QTableWidgetItem(f"{row['pl']:+.2f}")

            # Percentagem de P&L
            pct = (
                (row["current"] - row["entry"])
                / row["entry"]
                * (1 if row["side"] == "Long" else -1)
                * 100
            )
            pct_item = QTableWidgetItem(f"{pct:+.2f}%")

            # Cor conforme lucro/prejuízo
            color = (
                colors.ACCENT_GREEN
                if row["pl"] >= 0
                else colors.ACCENT_RED
            )

            for item in [
                symbol_item,
                side_item,
                entry_item,
                current_item,
                pl_item,
                pct_item,
            ]:
                item.setFont(typography.inter(10))
                item.setTextAlignment(Qt.AlignCenter)

            pl_item.setForeground(QColor(color))
            pct_item.setForeground(QColor(color))
            side_item.setForeground(QColor(color))

            # Inserir na tabela
            self.table.setItem(r, 0, symbol_item)
            self.table.setItem(r, 1, side_item)
            self.table.setItem(r, 2, entry_item)
            self.table.setItem(r, 3, current_item)
            self.table.setItem(r, 4, pl_item)
            self.table.setItem(r, 5, pct_item)


            # ==================================================
            # COLUNA DE AÇÕES (BOTÕES)
            # ==================================================

            action_widget = QWidget()
            h = QHBoxLayout(action_widget)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)

            for action, accent in [
                ("Close", colors.ACCENT_RED),
                ("Reduce", colors.HIGHLIGHT),
                ("Add", colors.ACCENT_GREEN),
            ]:
                btn = QPushButton(action)
                btn.setFixedHeight(22)
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background:{accent};
                        color:{colors.BACKGROUND};
                        border:none;
                        border-radius:4px;
                    }}
                    """
                )
                h.addWidget(btn)

            self.table.setCellWidget(r, 6, action_widget)


    def update_data(self, rows):
        """
        Hook genérico para dados externos (futuro).
        """
        self.populate(rows)


    # ======================================================
    # BARRA DE RESUMO INFERIOR
    # ======================================================

    def _build_summary_bar(self) -> QWidget:
        """
        Cria barra de métricas agregadas:
        - Total P&L
        - Win Rate
        - Nº posições abertas
        - Nº trades do dia
        """
        bar = QFrame()
        bar.setFrameShape(QFrame.NoFrame)
        bar.setStyleSheet(
            f"background-color:{colors.PANEL_BG};"
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(14)

        metrics = [
            ("Total P&L:", "+$1245.50", colors.ACCENT_GREEN),
            ("Win Rate:", "68.5%", colors.HIGHLIGHT),
            ("Open:", "2", colors.TEXT),
            ("Trades Today:", "14", colors.TEXT),
        ]

        for label_text, value_text, color in metrics:
            lbl = QLabel(label_text)
            lbl.setFont(typography.inter(10, QFont.DemiBold))
            lbl.setStyleSheet(f"color:{colors.MUTED};")

            val = QLabel(value_text)
            val.setFont(typography.mono(10, QFont.DemiBold))
            val.setStyleSheet(f"color:{color};")

            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            h.addWidget(lbl)
            h.addWidget(val)

            layout.addWidget(container)

        layout.addStretch()
        return bar
