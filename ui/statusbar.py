import random
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QStatusBar

from ui.theme import colors, typography


class StatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setStyleSheet("QStatusBar{padding:4px;}")

        self.provider_label = QLabel("Binance WS")
        self.cpu_label = QLabel("CPU: --%")
        self.mem_label = QLabel("MEM: --%")
        self.stream_label = QLabel("Market data streaming")
        self.update_label = QLabel("Last update: --:--:--")

        for lbl in [
            self.provider_label,
            self.cpu_label,
            self.mem_label,
            self.stream_label,
            self.update_label,
        ]:
            lbl.setFont(typography.inter(11))
            lbl.setStyleSheet(f"color: {colors.MUTED};")
            self.addPermanentWidget(lbl)

        self.connection_label = QLabel("Connected")
        self.connection_label.setFont(typography.inter(11))
        self.connection_label.setStyleSheet(f"color: {colors.ACCENT_GREEN};")
        self.addWidget(self.connection_label)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_metrics)
        self.timer.start(1500)

    def _update_metrics(self):
        cpu = random.randint(30, 60)
        mem = random.randint(40, 75)
        now = time.strftime("%H:%M:%S")
        self.cpu_label.setText(f"CPU: {cpu}%")
        self.mem_label.setText(f"MEM: {mem}%")
        self.update_label.setText(f"Last update: {now}")

    def update_data(self, data):  # placeholder for integration
        pass

    def refresh_styles(self):
        for lbl in [
            self.provider_label,
            self.cpu_label,
            self.mem_label,
            self.stream_label,
            self.update_label,
        ]:
            lbl.setStyleSheet(f"color: {colors.MUTED};")
        self.connection_label.setStyleSheet(f"color: {colors.ACCENT_GREEN};")
