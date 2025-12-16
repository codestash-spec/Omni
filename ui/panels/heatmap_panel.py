# ==========================================================
# IMPORTS STANDARD
# ==========================================================

import random
import logging

# ==========================================================
# IMPORTS QT (GRÁFICOS)
# ==========================================================

from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QTimer

# ==========================================================
# TEMA DA UI
# ==========================================================

from ui.theme import colors, typography


# ==========================================================
# HEATMAP VIEW (CAMADA GRÁFICA)
# ==========================================================

class HeatmapView(QGraphicsView):
    """
    Vista gráfica do heatmap de liquidez.

    Responsabilidades:
    - Desenhar células (retângulos) coloridas
    - Permitir zoom com scroll
    - Permitir pan (drag)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Ativar antialiasing para melhor qualidade visual
        self.setRenderHint(QPainter.Antialiasing, True)

        # Cena gráfica Qt
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # Interação
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # Dimensões do heatmap (dummy)
        self.rows = 10
        self.cols = 80

        # Dimensões de cada célula
        self.cell_width = 12
        self.cell_height = 26

        # População inicial com dados fictícios
        self.populate(self._dummy_data())


    # ======================================================
    # DADOS FICTÍCIOS
    # ======================================================

    def _dummy_data(self):
        """
        Gera matriz de valores aleatórios [0..1].

        Cada valor representa intensidade de liquidez.
        """
        return [
            [random.random() for _ in range(self.cols)]
            for _ in range(self.rows)
        ]


    # ======================================================
    # RENDERIZAÇÃO DO HEATMAP
    # ======================================================

    def populate(self, data):
        """
        Renderiza o heatmap a partir de uma matriz 2D.
        """
        self.scene.clear()

        for y, row in enumerate(data):
            for x, value in enumerate(row):
                # Converter intensidade em valor de cor
                intensity = int(80 + value * 140)

                rect = QGraphicsRectItem(
                    x * self.cell_width,
                    y * self.cell_height,
                    self.cell_width,
                    self.cell_height,
                )

                # Cor baseada na intensidade
                rect.setBrush(
                    QColor(colors.ACCENT_BLUE).darker(intensity)
                )

                # Contorno discreto
                rect.setPen(QColor(colors.BACKGROUND))

                self.scene.addItem(rect)

        # Definir área total da cena
        self.setSceneRect(
            0,
            0,
            self.cols * self.cell_width,
            self.rows * self.cell_height,
        )


    def update_heatmap(self, data):
        """
        API pública para atualizar o heatmap.
        """
        self.populate(data)


    # ======================================================
    # ZOOM COM SCROLL
    # ======================================================

    def wheelEvent(self, event):
        """
        Zoom in / out com o scroll do rato.
        """
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale(factor, factor)
        super().wheelEvent(event)


# ==========================================================
# HEATMAP PANEL (WIDGET)
# ==========================================================

class HeatmapPanel(QWidget):
    """
    Painel de Heatmap de Liquidez.

    Objetivo:
    - Visualizar concentração de ordens (DOM / depth)
    - Ajudar a identificar zonas de liquidez

    Estado atual:
    - Dados fictícios
    - Estrutura pronta para depth real
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Nome do widget (docks / estilos)
        self.setObjectName("HeatmapPanel")

        # Logger local
        self._logger = logging.getLogger(__name__)

        # Timer para refresh de dados dummy
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(2000)
        self._refresh_timer.timeout.connect(self._refresh_dummy_data)


        # ==================================================
        # LAYOUT PRINCIPAL
        # ==================================================

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Título
        lbl = QLabel("Liquidity Heatmap")
        lbl.setFont(typography.inter(11))
        lbl.setStyleSheet(f"color:{colors.TEXT};")
        layout.addWidget(lbl)

        # Vista gráfica
        self.view = HeatmapView()
        layout.addWidget(self.view)


        # ==================================================
        # LEGENDA
        # ==================================================

        legend = QHBoxLayout()

        legend_label = QLabel("Volume Intensity (DUMMY DATA)")
        legend_label.setFont(typography.inter(10))
        legend_label.setStyleSheet(f"color:{colors.MUTED};")

        legend.addWidget(legend_label)
        legend.addStretch()

        layout.addLayout(legend)


        # ==================================================
        # INIT
        # ==================================================

        self._wire_engine()
        self._refresh_timer.start()


    # ======================================================
    # DADOS FICTÍCIOS
    # ======================================================

    def _refresh_dummy_data(self):
        """
        Gera novos dados fictícios periodicamente.
        """
        dummy_data = [
            [random.random() for _ in range(self.view.cols)]
            for _ in range(self.view.rows)
        ]
        self.view.update_heatmap(dummy_data)


    # ======================================================
    # LIGAÇÃO AO CORE DATA ENGINE
    # ======================================================

    def _wire_engine(self, attempts=0):
        """
        Liga o painel ao CoreDataEngine quando disponível.
        """
        window = self.window()
        engine = getattr(window, "data_engine", None) if window else None

        if engine:
            try:
                engine.depth_snapshot.connect(self._on_depth)
                engine.depth_update.connect(self._on_depth)
                self._logger.info("HeatmapPanel wired to CoreDataEngine")
            except Exception as e:
                self._logger.warning("HeatmapPanel wire failed: %s", e)
        elif attempts < 3:
            QTimer.singleShot(
                200,
                lambda: self._wire_engine(attempts + 1),
            )


    # ======================================================
    # EVENT HANDLERS (FUTURO)
    # ======================================================

    def _on_depth(self, evt):
        """
        Handler para dados reais de depth.
        Aqui será calculada a intensidade de liquidez.
        """
        pass


    # ======================================================
    # API PÚBLICA
    # ======================================================

    def update_data(self, data):
        """
        Atualiza o heatmap externamente.
        """
        self.view.update_heatmap(data)
