from PySide6.QtGui import QColor
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ui.theme import colors, typography


class NewsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NewsPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        layout.addWidget(self.list)
        self.populate(self._dummy_news())

    def _dummy_news(self):
        return [
            "Fed Chair speech at 14:00 GMT",
            "CME announces extended trading hours for metals",
            "OPEC+ hints at further production cuts",
            "U.S. CPI beats expectations; yields surge",
            "Tech earnings surprise to upside",
        ]

    def populate(self, items):
        self.list.clear()
        for item in items:
            row = QListWidgetItem(item)
            row.setFont(typography.inter(10))
            row.setForeground(QColor(colors.TEXT))
            self.list.addItem(row)

    def update_data(self, items):
        self.populate(items)
