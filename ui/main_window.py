# ==========================================================
# IMPORTS DE SISTEMA / LOGGING
# ==========================================================

import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


# ==========================================================
# IMPORTS QT (PySide6)
# ==========================================================

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QWidget,
    QMenuBar,
    QDockWidget,
)

from PySide6.QtCore import (
    QSettings,
    QStandardPaths,
    Qt,
    qInstallMessageHandler,
    QTimer,
)

from PySide6.QtGui import QAction, QActionGroup


# ==========================================================
# CORE DA APLICAÇÃO
# ==========================================================

from core.app_state import AppState
from core.data_engine.core_engine import CoreDataEngine


# ==========================================================
# PAINÉIS DA UI
# ==========================================================

from ui.panels.chart_panel import ChartPanel
from ui.panels.dom_panel import DomPanel
from ui.panels.footprint_panel import FootprintPanel
from ui.panels.heatmap_panel import HeatmapPanel
from ui.panels.marketwatch_panel import MarketWatchPanel
from ui.panels.microstructure_panel import MicrostructurePanel
from ui.panels.news_panel import NewsPanel
from ui.panels.positions_panel import PositionsPanel
from ui.panels.strategy_signals_panel import StrategySignalsPanel
from ui.panels.tape_panel import TapePanel
from ui.panels.volume_profile_panel import VolumeProfilePanel


# ==========================================================
# COMPONENTES DE UI
# ==========================================================

from ui.statusbar import StatusBar
from ui.topbar import TopBar
from ui.window_layout import apply_default_layout, create_dock
from ui.settings_dialog import SettingsDialog
from ui.theme.theme_manager import ThemeManager


# ==========================================================
# CLASSE PRINCIPAL DA APP
# ==========================================================

class MainWindow(QMainWindow):
    """
    Janela principal do OmniFlow Terminal.
    Responsável por:
    - criar menus
    - criar painéis
    - gerir layouts
    - ligar CoreDataEngine à UI
    """

    def __init__(self):
        super().__init__()

        # --------------------------------------------------
        # Logger local
        # --------------------------------------------------
        self._logger = logging.getLogger(__name__)
        self._dock_debug = False

        self.setWindowTitle("OmniFlow Terminal")


        # ==================================================
        # CONFIGURAÇÃO DE DOCKS
        # ==================================================

        self.setDockOptions(
            QMainWindow.AllowTabbedDocks |
            QMainWindow.AllowNestedDocks
        )
        self.setDockNestingEnabled(True)


        # ==================================================
        # ESTADO GLOBAL + DATA ENGINE
        # ==================================================

        self.app_state = AppState()

        self.data_engine = CoreDataEngine(
            self,
            initial_symbol=self.app_state.current_symbol,
            initial_timeframe="1m"
        )


        # ==================================================
        # SETTINGS / THEME
        # ==================================================

        self.settings = QSettings("OmniFlow", "TerminalUI")
        self.theme_manager = ThemeManager(self.settings)
        self.current_theme = self.theme_manager.apply_saved(self)


        # ==================================================
        # MENU BAR + TOP BAR
        # ==================================================

        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        self.topbar = TopBar(self)
        self._build_menus(menu_bar)


        # ==================================================
        # STATUS BAR
        # ==================================================

        self.status = StatusBar(self)
        self.setStatusBar(self.status)


        # ==================================================
        # TOPBAR COMO DOCK FIXO
        # ==================================================

        topbar_dock = QDockWidget("", self)
        topbar_dock.setObjectName("topbar_dock")
        topbar_dock.setWidget(self.topbar)
        topbar_dock.setTitleBarWidget(QWidget())
        topbar_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        topbar_dock.setAllowedAreas(Qt.TopDockWidgetArea)
        self.addDockWidget(Qt.TopDockWidgetArea, topbar_dock)


        # ==================================================
        # CENTRAL WIDGET
        # ==================================================

        self.setCentralWidget(QWidget())


        # ==================================================
        # PAINÉIS
        # ==================================================

        self.chart_panel = ChartPanel(self)
        self.footprint_panel = FootprintPanel(self)
        self.tape_panel = TapePanel(self)
        self.dom_ladder = DomPanel(self)
        self.heatmap_panel = HeatmapPanel(self)
        self.volume_profile_panel = VolumeProfilePanel(self)
        self.microstructure_panel = MicrostructurePanel(self)
        self.strategy_panel = StrategySignalsPanel(self)
        self.news_panel = NewsPanel(self)
        self.positions_panel = PositionsPanel(self)

        market_panel = MarketWatchPanel(self)


        # ==================================================
        # DOCKS
        # ==================================================

        self.docks = {
            "marketwatch": create_dock(self, market_panel, "MarketWatch", "dock_marketwatch"),
            "price_chart": create_dock(self, self.chart_panel, "Price Chart", "dock_price_chart"),
            "time_sales": create_dock(self, self.tape_panel, "Tape Reading", "dock_time_sales"),
            "footprint": create_dock(self, self.footprint_panel, "Footprint", "dock_footprint"),
            "dom_ladder": create_dock(self, self.dom_ladder, "DOM Ladder", "dock_dom_ladder"),
            "volume_profile": create_dock(self, self.volume_profile_panel, "Volume Profile", "dock_volume_profile"),
            "heatmap_panel": create_dock(self, self.heatmap_panel, "Heat Map", "dock_heatmap_panel"),
            "microstructure_panel": create_dock(self, self.microstructure_panel, "Micro Structure", "dock_microstructure_panel"),
            "news_panel": create_dock(self, self.news_panel, "News", "dock_news_panel"),
            "strategy_panel": create_dock(self, self.strategy_panel, "Strategies", "dock_strategy_panel"),
            "positions_panel": create_dock(self, self.positions_panel, "Positions", "dock_positions"),
        }


        # ==================================================
        # LIGAÇÕES CORE ↔ UI
        # ==================================================

        market_panel.bind_state(self.app_state)

        self.app_state.symbol_changed.connect(self.data_engine.set_symbol)
        self.chart_panel.timeframe_changed.connect(self.data_engine.set_timeframe)

        self.data_engine.candle_history.connect(
            lambda evt: self.chart_panel.set_history(evt.candles)
        )
        self.data_engine.candle_update.connect(
            lambda evt: self.chart_panel.on_candle_update(evt.candle, evt.closed)
        )

        self.data_engine.trade.connect(
            lambda evt: self.tape_panel.on_trade(evt.trade)
        )


        # ==================================================
        # MENUS
        # ==================================================

        self._build_view_menu()
        self._wire_theme_menu()
        self._wire_file_menu()


        # ==================================================
        # APLICAR LAYOUT DEFAULT (DEPOIS DO SHOW)
        # ==================================================

        QTimer.singleShot(0, lambda: apply_default_layout(self, self.docks))


        # ==================================================
        # START DATA ENGINE
        # ==================================================

        if not os.environ.get("OMNIFLOW_DISABLE_PROVIDER"):
            QTimer.singleShot(0, self.data_engine.start)


    # ======================================================
    # MENUS
    # ======================================================

    def _build_menus(self, menu_bar):
        file_menu = menu_bar.addMenu("File")
        for action in self.topbar.file_actions.values():
            file_menu.addAction(action)

        self.topbar.view_menu = menu_bar.addMenu("View")

        tools_menu = menu_bar.addMenu("Tools")
        for action in self.topbar.tools_actions.values():
            tools_menu.addAction(action)


    def _build_view_menu(self):
        view_menu = self.topbar.view_menu
        view_menu.clear()

        self._view_actions = {}

        for key, dock in self.docks.items():
            action = QAction(dock.windowTitle(), self)
            action.setCheckable(True)
            action.setChecked(True)

            # MENU → DOCK
            action.toggled.connect(
                lambda checked, d=dock: self._toggle_dock_safe(d, checked)
            )

            view_menu.addAction(action)
            self._view_actions[dock] = action



    def _wire_theme_menu(self):
        for name, action in self.topbar.theme_actions.items():
            action.setChecked(name == self.current_theme)
            action.triggered.connect(
                lambda _, n=name: self.theme_manager.apply(self, n)
            )


    def _wire_file_menu(self):
        actions = self.topbar.file_actions

        if "new_workspace" in actions:
            actions["new_workspace"].triggered.connect(
                lambda: apply_default_layout(self, self.docks)
            )

        if "exit" in actions:
            actions["exit"].triggered.connect(self.close)

    def _toggle_dock_safe(self, dock: QDockWidget, visible: bool):
        """
        Toggle seguro de docks.
        NÃO reage a visibilityChanged causado por tabs.
        """

        if visible:
            dock.show()
            dock.raise_()
        else:
            dock.hide()


# ==========================================================
# FUNÇÃO RUN — ENTRY POINT DA APLICAÇÃO
# ==========================================================

def run():
    """
    Entry point do OmniFlow Terminal.
    Mantido aqui para compatibilidade com main.py
    """

    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
