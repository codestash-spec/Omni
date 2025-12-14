import random


from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QAction
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMenuBar,
    QWidget,
)

from ui.theme import colors, typography


class TopBar(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")

        self.menu_bar = QMenuBar(self)
        self._build_menus()

        self.title_label = QLabel("OmniFlow Terminal")
        self.title_label.setFont(typography.inter(16, QFont.DemiBold))
        self.title_label.setStyleSheet(f"color: {colors.TEXT};")

        self.asset_label = QLabel("Asset Class:")
        self.asset_label.setFont(typography.inter(11, QFont.DemiBold))
        self.asset_label.setStyleSheet(f"color: {colors.MUTED};")

        self.asset_class_combo = QComboBox()
        self.asset_class_combo.addItems(["Crypto", "Futures", "Forex", "Equities"])
        self.asset_class_combo.setCurrentText("Crypto")
        self.asset_class_combo.setFixedWidth(130)

        self.sim_badge = QLabel("SIM")
        self.sim_badge.setFont(typography.inter(11, QFont.DemiBold))
        self.sim_badge.setAlignment(Qt.AlignCenter)
        self.sim_badge.setFixedWidth(48)
        self.sim_badge.setStyleSheet(
            f"color:{colors.BACKGROUND}; background:{colors.HIGHLIGHT}; border-radius:4px; padding:2px 6px;"
        )

        self.latency_label = QLabel("Latency: --ms")
        self.fps_label = QLabel("FPS: --")
        for lbl in (self.latency_label, self.fps_label):
            lbl.setFont(typography.mono(11, QFont.DemiBold))
            lbl.setStyleSheet(f"color: {colors.MUTED};")

        self.connection_label = QLabel("Connected")
        self.connection_label.setFont(typography.inter(12, QFont.DemiBold))
        self.connection_label.setStyleSheet(f"color: {colors.ACCENT_GREEN};")
        self.connection_label.setContentsMargins(4, 0, 0, 0)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)
        layout.addWidget(self.menu_bar)
        layout.addWidget(self.title_label)
        layout.addSpacing(12)
        layout.addWidget(self.asset_label)
        layout.addWidget(self.asset_class_combo)
        layout.addSpacing(8)
        layout.addWidget(self.sim_badge)
        layout.addStretch()
        layout.addWidget(self.latency_label)
        layout.addWidget(self.fps_label)
        layout.addSpacing(8)
        layout.addWidget(self.connection_label)

        self.metric_timer = QTimer(self)
        self.metric_timer.timeout.connect(self._update_metrics)
        self.metric_timer.start(1000)

    def _build_menus(self):
        file_menu = self.menu_bar.addMenu("File")
        self.file_actions = {
            "new_workspace": QAction("New Workspace", self),
            "open_workspace": QAction("Open Workspace", self),
            "save_workspace": QAction("Save Workspace", self),
            "save_workspace_as": QAction("Save Workspace As…", self),
            "exit": QAction("Exit", self),
        }
        file_menu.addSeparator()
        self.file_actions["exit"] = file_menu.addAction("Exit")

        self.view_menu = self.menu_bar.addMenu("View")
        self.view_actions = {}
        self.theme_actions = {}

        trading_menu = self.menu_bar.addMenu("Trading")
        trading_menu.addAction("Connect")
        trading_menu.addAction("Disconnect")
        exec_mode_menu = QMenu("Execution Mode (SIM / LIVE)", self)
        exec_mode_menu.addAction("SIM")
        exec_mode_menu.addAction("LIVE")
        trading_menu.addMenu(exec_mode_menu)

        tools_menu = self.menu_bar.addMenu("Tools")
        self.tools_actions = {
            "settings": tools_menu.addAction("Settings"),
            "layout_manager": tools_menu.addAction("Layout Manager"),
            "layout_debug": tools_menu.addAction("Layout Debug -> Dump Now"),
        }

        help_menu = self.menu_bar.addMenu("Help")
        help_menu.addAction("About")

    def _update_metrics(self):
        latency = random.randint(8, 24)
        fps = random.choice([58, 59, 60, 61])
        self.latency_label.setText(f"Latency: {latency}ms")
        self.fps_label.setText(f"FPS: {fps}")

    def update_data(self, data):  # placeholder for future hookups
        pass

    def refresh_styles(self):
        self.title_label.setStyleSheet(f"color: {colors.TEXT};")
        self.asset_label.setStyleSheet(f"color: {colors.MUTED};")
        self.sim_badge.setStyleSheet(
            f"color:{colors.BACKGROUND}; background:{colors.HIGHLIGHT}; border-radius:4px; padding:2px 6px;"
        )
        for lbl in (self.latency_label, self.fps_label):
            lbl.setStyleSheet(f"color: {colors.MUTED};")
        self.connection_label.setStyleSheet(f"color: {colors.ACCENT_GREEN};")
