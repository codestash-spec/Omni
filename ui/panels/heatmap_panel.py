import random
import logging

from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer

from ui.theme import colors, typography


class HeatmapView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.rows = 10
        self.cols = 80
        self.cell_width = 12
        self.cell_height = 26
        self.populate(self._dummy_data())

    def _dummy_data(self):
        return [[random.random() for _ in range(self.cols)] for _ in range(self.rows)]

    def populate(self, data):
        self.scene.clear()
        for y, row in enumerate(data):
            for x, value in enumerate(row):
                intensity = int(80 + value * 140)
                rect = QGraphicsRectItem(
                    x * self.cell_width,
                    y * self.cell_height,
                    self.cell_width,
                    self.cell_height,
                )
                rect.setBrush(QColor(colors.ACCENT_BLUE).darker(intensity))
                rect.setPen(QColor(colors.BACKGROUND))
                self.scene.addItem(rect)
        self.setSceneRect(0, 0, self.cols * self.cell_width, self.rows * self.cell_height)

    def update_heatmap(self, data):
        self.populate(data)

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale(factor, factor)
        super().wheelEvent(event)


class HeatmapPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeatmapPanel")
        self._logger = logging.getLogger(__name__)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(2000)
        self._refresh_timer.timeout.connect(self._refresh_dummy_data)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        lbl = QLabel("Liquidity Heatmap")
        lbl.setFont(typography.inter(11))
        lbl.setStyleSheet(f"color:{colors.TEXT};")
        layout.addWidget(lbl)
        self.view = HeatmapView()
        layout.addWidget(self.view)

        legend = QHBoxLayout()
        legend_label = QLabel("Volume Intensity (DUMMY DATA)")
        legend_label.setFont(typography.inter(10))
        legend_label.setStyleSheet(f"color:{colors.MUTED};")
        legend.addWidget(legend_label)
        legend.addStretch()
        layout.addLayout(legend)

        self._wire_engine()
        self._refresh_timer.start()

    def _refresh_dummy_data(self):
        """Generate dummy data for visualization."""
        dummy_data = [[random.random() for _ in range(self.view.cols)] for _ in range(self.view.rows)]
        self.view.update_heatmap(dummy_data)

    def _wire_engine(self, attempts=0):
        """Hook to CoreDataEngine when ready."""
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
            QTimer.singleShot(200, lambda: self._wire_engine(attempts + 1))

    def _on_depth(self, evt):
        """Will update heatmap with real depth data."""
        pass

    def update_data(self, data):
        self.view.update_heatmap(data)
