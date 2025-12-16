# ==========================================================
# IMPORTS QT
# ==========================================================

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


# ==========================================================
# TEMA DA UI
# ==========================================================

from ui.theme import colors, typography


# ==========================================================
# NEWS PANEL
# ==========================================================

class NewsPanel(QWidget):
    """
    Painel de notícias / eventos macro.

    Estado atual:
    - lista simples (QListWidget)
    - conteúdo dummy (estático)
    - sem ligação a feeds externos

    Futuro:
    - integração com calendários económicos (CPI, NFP, FOMC)
    - integração com news feeds (Reuters / RSS / API)
    - filtros por impacto, país, ativo
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Nome do widget (usado para estilos / docking)
        self.setObjectName("NewsPanel")


        # ==================================================
        # LAYOUT PRINCIPAL
        # ==================================================

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)


        # ==================================================
        # LISTA DE NOTÍCIAS
        # ==================================================

        self.list = QListWidget()

        # Ativar cores alternadas para melhor legibilidade
        self.list.setAlternatingRowColors(True)

        layout.addWidget(self.list)


        # ==================================================
        # POPULAR COM DADOS FICTÍCIOS
        # ==================================================

        self.populate(self._dummy_news())


    # ======================================================
    # DADOS FICTÍCIOS
    # ======================================================

    def _dummy_news(self):
        """
        Retorna uma lista de notícias/eventos fictícios.

        Serve apenas para:
        - validar layout
        - testar scrolling
        - testar integração visual com o resto da UI
        """
        return [
            "Fed Chair speech at 14:00 GMT",
            "CME announces extended trading hours for metals",
            "OPEC+ hints at further production cuts",
            "U.S. CPI beats expectations; yields surge",
            "Tech earnings surprise to upside",
        ]


    # ======================================================
    # RENDERIZAÇÃO
    # ======================================================

    def populate(self, items):
        """
        Preenche a lista de notícias.
        """
        self.list.clear()

        for item in items:
            row = QListWidgetItem(item)

            # Fonte institucional
            row.setFont(typography.inter(10))

            # Cor padrão de texto
            row.setForeground(QColor(colors.TEXT))

            self.list.addItem(row)


    def update_data(self, items):
        """
        Hook genérico para dados externos (futuro).
        """
        self.populate(items)
