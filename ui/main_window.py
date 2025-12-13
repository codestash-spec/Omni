import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import sys

from PySide6.QtCore import QByteArray, QSettings, QStandardPaths, Qt, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QWidget

from core.app_state import AppState
from core.data_engine.core_engine import CoreDataEngine

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
from ui.statusbar import StatusBar
from ui.theme import colors
from ui.theme.theme_manager import ThemeManager
from ui.topbar import TopBar
from ui.window_layout import apply_default_layout, create_dock
from ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self._dock_debug = False
        self.setWindowTitle("OmniFlow Terminal")
        self.setMinimumSize(1400, 900)
        self.setDockOptions(
            QMainWindow.AllowTabbedDocks
            | QMainWindow.AllowNestedDocks
        )
        self.setDockNestingEnabled(True)

        self.app_state = AppState()
        self.data_engine = CoreDataEngine(self, initial_symbol=self.app_state.current_symbol, initial_timeframe="1m")

        self.settings = QSettings("OmniFlow", "TerminalUI")
        self.layout_version = "20241215-r4"
        self.theme_manager = ThemeManager(self.settings)
        self.current_theme = self.theme_manager.apply_saved(self)

        base_config = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not base_config:
            base_config = str(Path.home() / ".omniflow_terminal")
        self.layout_dir = Path(base_config)
        self.layout_dir.mkdir(parents=True, exist_ok=True)
        self.default_layout_path = self.layout_dir / "default_layout.bin"

        self.topbar = TopBar(self)
        self.setMenuWidget(self.topbar)
        self.status = StatusBar(self)
        self.setStatusBar(self.status)

        self._central_placeholder = QWidget(self)
        self.setCentralWidget(self._central_placeholder)

        # Panels
        chart_panel = ChartPanel(self)
        self.chart_panel = chart_panel
        dom_panel = DomPanel(self)
        self.dom_panel = dom_panel
        footprint_panel = FootprintPanel(self)
        tape_panel = TapePanel(self)
        self.tape_panel = tape_panel
        heatmap_panel = HeatmapPanel(self)
        volume_profile_panel = VolumeProfilePanel(self)
        self.volume_profile_panel = volume_profile_panel
        microstructure_panel = MicrostructurePanel(self)
        strategy_panel = StrategySignalsPanel(self)
        market_panel = MarketWatchPanel(self)
        news_panel = NewsPanel(self)
        positions_panel = PositionsPanel(self)

        # Docks
        self.docks = {
            "strategy_signals": create_dock(self, strategy_panel, "Strategy Signals", "dock_strategy_signals", Qt.LeftDockWidgetArea),
            "price_chart": create_dock(self, chart_panel, "Price Chart", "dock_price_chart", Qt.TopDockWidgetArea),
            "dom_ladder": create_dock(self, dom_panel, "DOM Ladder", "dock_dom_ladder", Qt.RightDockWidgetArea),
            "marketwatch": create_dock(self, market_panel, "MarketWatch", "dock_marketwatch", Qt.LeftDockWidgetArea),
            "positions": create_dock(self, positions_panel, "Positions / Orders", "dock_positions", Qt.LeftDockWidgetArea),
            "news": create_dock(self, news_panel, "News Feed", "dock_news", Qt.LeftDockWidgetArea),
            "liquidity_heatmap": create_dock(self, heatmap_panel, "Liquidity Heatmap", "dock_liquidity_heatmap", Qt.BottomDockWidgetArea),
            "microstructure": create_dock(self, microstructure_panel, "Microstructure", "dock_microstructure", Qt.BottomDockWidgetArea),
            "time_sales": create_dock(self, tape_panel, "Tape Reading", "dock_time_sales", Qt.BottomDockWidgetArea),
            "footprint": create_dock(self, footprint_panel, "Footprint Cluster", "dock_footprint", Qt.RightDockWidgetArea),
            "volume_profile": create_dock(self, volume_profile_panel, "Volume Profile", "dock_volume_profile", Qt.RightDockWidgetArea),
        }
        self._wire_dock_debug()

        # Data wiring: MarketWatch from ticker bus; chart/tape via DataEngine
        market_panel.bind_state(self.app_state)
        self.app_state.symbol_changed.connect(self.data_engine.set_symbol)
        chart_panel.timeframe_changed.connect(self.data_engine.set_timeframe)

        # Core signal wiring (direct to panels)
        self.data_engine.tickers.connect(lambda evt: market_panel.update_data(evt.tickers))
        self.data_engine.symbol_changed.connect(lambda evt: self._on_symbol_changed(evt.symbol, chart_panel, tape_panel))
        self.data_engine.candle_history.connect(lambda evt: chart_panel.set_history(evt.candles))
        self.data_engine.candle_update.connect(lambda evt: chart_panel.on_candle_update(evt.candle, evt.closed))
        # Tape panel expects TradeEvent
        self.data_engine.trade.connect(lambda evt: tape_panel.on_trade(evt.trade))
        # Forward depth events directly to DOM panel
        if hasattr(self, "dom_panel"):
            self.data_engine.depth_snapshot.connect(self.dom_panel.on_depth_snapshot)
            self.data_engine.depth_update.connect(self.dom_panel.on_depth_update)
            # also forward trades for last price tracking
            self.data_engine.trade.connect(lambda evt: self.dom_panel.on_trade_event(evt))
        # Ensure VolumeProfile receives trade/candle signals directly
        if hasattr(self, "volume_profile_panel"):
            self.data_engine.trade.connect(self.volume_profile_panel._on_trade)
            self.data_engine.candle_history.connect(self.volume_profile_panel._on_candle_history)
            self.data_engine.candle_update.connect(self.volume_profile_panel._on_candle_update)
            self.data_engine.timeframe_changed.connect(self.volume_profile_panel._on_timeframe_changed)
            self.data_engine.symbol_changed.connect(self.volume_profile_panel._on_symbol_changed)

        self.default_visible = {
            # All views enabled by default
        }

        self._build_view_menu()
        self._wire_theme_menu()
        self._wire_file_menu()
        self._wire_tools_menu()
        self.apply_startup_layout()
        # Allow disabling network/providers during local debugging/tests by setting
        # OMNIFLOW_DISABLE_PROVIDER=1 in the environment. This avoids provider
        # threads or event-loops interfering with GUI visibility checks.
        if not os.environ.get("OMNIFLOW_DISABLE_PROVIDER"):
            self.data_engine.start()

    def _on_depth_snapshot(self, evt):
        """Global depth snapshot handler for all panels."""
        # Forward to DOM and other interested panels
        try:
            if hasattr(self, "dom_panel"):
                self.dom_panel.on_depth_snapshot(evt)
            if hasattr(self, "volume_profile_panel") and hasattr(self.volume_profile_panel, "_pending"):
                # volume profile doesn't consume depth but may rebalance UI
                self.volume_profile_panel._pending = True
        except Exception:
            self._logger.exception("Error forwarding depth snapshot")

    def _on_depth_update(self, evt):
        """Global depth update handler for all panels."""
        try:
            if hasattr(self, "dom_panel"):
                self.dom_panel.on_depth_update(evt)
            if hasattr(self, "volume_profile_panel") and hasattr(self.volume_profile_panel, "_pending"):
                self.volume_profile_panel._pending = True
        except Exception:
            self._logger.exception("Error forwarding depth update")

    def apply_startup_layout(self):
        geom_key = "geometry"
        state_key = "state"
        default_geom_key = "default_geometry"
        default_state_key = "default_state"
        version_key = "layout_version"

        geometry = self.settings.value(geom_key)
        state = self.settings.value(state_key)
        default_geometry = self.settings.value(default_geom_key)
        default_state = self.settings.value(default_state_key)
        stored_version = self.settings.value(version_key)

        # If the stored version does not match, ignore any persisted layout (including defaults)
        if stored_version != self.layout_version:
            for k in (geom_key, state_key, default_geom_key, default_state_key):
                self.settings.remove(k)
            geometry = None
            state = None
            default_geometry = None
            default_state = None

        layout_loaded = False
        if stored_version == self.layout_version and geometry and state:
            if self.restoreGeometry(geometry) and self.restoreState(state):
                layout_loaded = True

        if not layout_loaded:
            fallback_geometry, fallback_state = self._load_default_layout(default_geometry, default_state)
            if fallback_state and self.restoreState(fallback_state):
                if fallback_geometry:
                    self.restoreGeometry(fallback_geometry)
                layout_loaded = True

        if not layout_loaded:
            self.apply_default_layout_all_views(save_as_default=True)
        else:
            if not self._is_layout_valid():
                self.apply_default_layout_all_views(save_as_default=True)
            else:
                self._remember_active_layout(self.saveGeometry(), self.saveState())
                self.settings.setValue(version_key, self.layout_version)
        self._sync_theme_actions()
        self._sync_view_actions()

    def _apply_and_store_default(self):
        self.apply_default_layout_all_views(save_as_default=True)

    def apply_default_layout_all_views(self, save_as_default: bool = False, show_all: bool = False):
        # Rebuild the docking graph from scratch to avoid inheriting corrupted positions
        self.setUpdatesEnabled(False)
        for dock in self.docks.values():
            dock.setFloating(False)
            try:
                self.removeDockWidget(dock)
            except Exception:
                pass
        apply_default_layout(self, self.docks)
        # Show all views by default so user can reorganize immediately
        for key, dock in self.docks.items():
            dock.setVisible(True)
            dock.show()
            dock.raise_()
        QApplication.processEvents()
        geom = self.saveGeometry()
        st = self.saveState()
        if save_as_default:
            self._persist_default_layout(geom, st)
        self._remember_active_layout(geom, st)
        self.setUpdatesEnabled(True)
        self._sync_view_actions()

    def _remember_active_layout(self, geometry: QByteArray, state: QByteArray):
        self.settings.setValue("geometry", geometry)
        self.settings.setValue("state", state)
        self.settings.setValue("layout_version", self.layout_version)

    def _persist_default_layout(self, geometry: QByteArray, state: QByteArray):
        self.settings.setValue("default_geometry", geometry)
        self.settings.setValue("default_state", state)
        self._write_layout_file(self.default_layout_path, geometry, state)

    def _load_default_layout(self, settings_geometry, settings_state):
        if settings_state:
            return settings_geometry, settings_state
        return self._read_layout_file(self.default_layout_path)

    def _write_layout_file(self, path: Path, geometry: QByteArray, state: QByteArray):
        try:
            payload = len(geometry).to_bytes(8, "big") + bytes(geometry) + bytes(state)
            path.write_bytes(payload)
        except OSError:
            pass

    def _read_layout_file(self, path: Path):
        if not path.exists():
            return None, None
        try:
            data = path.read_bytes()
        except OSError:
            return None, None
        if len(data) < 8:
            return None, None
        geom_len = int.from_bytes(data[:8], "big")
        geom_start = 8
        geom_end = geom_start + geom_len
        if geom_len < 0 or geom_end > len(data):
            return None, None
        geometry = QByteArray(data[geom_start:geom_end])
        state_bytes = data[geom_end:]
        if not state_bytes:
            return None, None
        state = QByteArray(state_bytes)
        return geometry, state

    def _build_view_menu(self):
        view_menu = getattr(self.topbar, "view_menu", None)
        if not view_menu:
            return
        view_menu.clear()
        self.view_actions = {}
        labels = {
            "price_chart": "Price Chart",
            "marketwatch": "MarketWatch",
            "positions": "Positions / Orders",
            "time_sales": "Time & Sales",
            "strategy_signals": "Strategy Signals",
            "news": "News Feed",
            "dom_ladder": "DOM Ladder",
            "footprint": "Footprint Cluster",
            "volume_profile": "Volume Profile",
            "liquidity_heatmap": "Liquidity Heatmap",
            "microstructure": "Microstructure",
        }
        for key, label in labels.items():
            dock = self.docks.get(key)
            if not dock:
                continue
            action = QAction(f"Toggle {label}", self)
            action.setCheckable(True)
            action.setChecked(True)
            view_menu.addAction(action)
            self.view_actions[key] = action
            action.toggled.connect(lambda checked, k=key, d=dock: self._toggle_dock(k, d, checked))
            dock.setVisible(True)
            dock.show()
            dock.raise_()
            dock.visibilityChanged.connect(lambda vis, a=action: self._sync_action_state(a, vis))
        view_menu.addSeparator()
        show_all = QAction("Show All Panels", self)
        reset_layout = QAction("Reset Layout to Default", self)
        show_all.triggered.connect(self._show_all_panels)
        reset_layout.triggered.connect(lambda: self.reset_layout())
        view_menu.addAction(show_all)
        view_menu.addAction(reset_layout)
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu("Theme")
        group = QActionGroup(self)
        group.setExclusive(True)
        self.topbar.theme_actions = {
            "default": theme_menu.addAction("Default"),
            "bloomberg": theme_menu.addAction("Bloomberg"),
            "refinitiv": theme_menu.addAction("Refinitiv"),
        }
        for action in self.topbar.theme_actions.values():
            action.setCheckable(True)
            group.addAction(action)
        self._sync_view_actions()

    def _wire_theme_menu(self):
        actions = getattr(self.topbar, "theme_actions", {})
        if not actions:
            return
        for name, action in actions.items():
            action.setChecked(name == self.current_theme)
            action.triggered.connect(lambda _checked, n=name: self._apply_theme(n))

    def _wire_file_menu(self):
        actions = getattr(self.topbar, "file_actions", {})
        if not actions:
            return
        if actions.get("new_workspace"):
            actions["new_workspace"].triggered.connect(self.reset_layout)
        if actions.get("open_workspace"):
            actions["open_workspace"].triggered.connect(self.load_layout)
        if actions.get("save_workspace"):
            actions["save_workspace"].triggered.connect(self.save_layout_as_default)
        if actions.get("save_workspace_as"):
            actions["save_workspace_as"].triggered.connect(self.save_layout_as)
        if actions.get("exit"):
            actions["exit"].triggered.connect(self.close)

    def _wire_tools_menu(self):
        tools = getattr(self.topbar, "tools_actions", {})
        settings_action = tools.get("settings")
        if settings_action:
            settings_action.triggered.connect(self._open_settings_dialog)
        layout_action = tools.get("layout_manager")
        if layout_action:
            layout_action.triggered.connect(self.reset_layout)
        debug_action = tools.get("layout_debug")
        if debug_action:
            debug_action.triggered.connect(lambda: self.debug_dump_docks("manual"))

    def save_layout_as(self):
        initial = str(self.layout_dir / "layout.bin")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Layout As",
            initial,
            "Layout Files (*.bin);;All Files (*.*)",
        )
        if path:
            geom = self.saveGeometry()
            st = self.saveState()
            self._write_layout_file(Path(path), geom, st)
            self._remember_active_layout(geom, st)

    def load_layout(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Layout",
            str(self.layout_dir),
            "Layout Files (*.bin);;All Files (*.*)",
        )
        if path:
            geom, st = self._read_layout_file(Path(path))
            if st:
                if geom:
                    self.restoreGeometry(geom)
                self.restoreState(st)
                self.ensure_all_views_visible()
                if not self._is_layout_valid():
                    self.apply_default_layout_all_views(save_as_default=False)
                else:
                    self._remember_active_layout(geom or self.saveGeometry(), st)

    def _on_symbol_changed(self, symbol: str, chart_panel: ChartPanel, tape_panel: TapePanel):
        self.app_state.set_symbol(symbol)
        chart_panel.set_symbol(symbol)
        tape_panel.set_symbol(symbol)

    def _open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == dialog.Accepted:
            # Reload tape preferences (size mode, thresholds, filters)
            if hasattr(self, "tape_panel"):
                self.tape_panel.reload_settings()

    def _apply_theme(self, theme: str):
        self.current_theme = self.theme_manager.apply(self, theme)
        self._sync_theme_actions()
        if hasattr(self, "topbar") and hasattr(self.topbar, "refresh_styles"):
            self.topbar.refresh_styles()
        if hasattr(self, "status") and hasattr(self.status, "refresh_styles"):
            self.status.refresh_styles()

    def _wire_dock_debug(self):
        if not self._dock_debug:
            return
        # Debug hooks to trace dock visibility/location/tabbing when dragging/tabbing
        for key, dock in self.docks.items():
            dock.visibilityChanged.connect(lambda vis, k=key, d=dock: self._log_dock("visibility", k, vis, d))
            dock.topLevelChanged.connect(lambda floating, k=key, d=dock: self._log_dock("floating", k, floating, d))
            dock.dockLocationChanged.connect(
                lambda area, k=key, d=dock: self._log_dock("area", k, area, d)
            )

    def _log_dock(self, event: str, key: str, val, dock):
        if not self._dock_debug:
            return
        tabbed_with = [d.objectName() for d in self.tabifiedDockWidgets(dock)]
        self._logger.info("Dock[%s] %s=%s tabbed_with=%s", key, event, val, tabbed_with)
        self._log_dock_snapshot()

    def _log_dock_snapshot(self):
        state = {}
        for name, dock in self.docks.items():
            tabbed = [d.objectName() for d in self.tabifiedDockWidgets(dock)]
            area = self.dockWidgetArea(dock)
            area_val = getattr(area, "value", area)
            state[name] = {
                "visible": dock.isVisible(),
                "floating": dock.isFloating(),
                "area": int(area_val) if isinstance(area_val, (int, float)) else str(area_val),
                "tabbed_with": tabbed,
            }
        if self._dock_debug:
            self._logger.debug("DockSnapshot: %s", state)

    def _force_show_all_docks(self):
        for dock in self.docks.values():
            dock.setVisible(True)
            dock.show()
            dock.raise_()
        QApplication.processEvents()

    def _is_layout_valid(self) -> bool:
        """
        Basic sanity check to detect corrupted/degenerate layouts.
        """
        for key, dock in self.docks.items():
            area = self.dockWidgetArea(dock)
            if area == Qt.NoDockWidgetArea:
                return False
            if not dock.isVisible() and key not in self.default_visible:
                return False
            geo = dock.geometry()
            if geo.width() < 40 or geo.height() < 40:
                return False
            if dock.isFloating() and (geo.right() < 0 or geo.bottom() < 0 or geo.x() > self.width() or geo.y() > self.height()):
                return False
        # Ensure critical right-column docks are present in the main docking area
        for key in ("dom_ladder", "volume_profile", "footprint"):
            dock = self.docks.get(key)
            if dock and self.dockWidgetArea(dock) == Qt.NoDockWidgetArea:
                return False
        return True

    def _toggle_dock(self, key: str, dock, checked: bool):
        if self._dock_debug:
            self._logger.debug("Action[view.%s] toggled=%s", key, checked)
        if checked:
            dock.show()
            dock.raise_()
        else:
            dock.hide()
        # keep the action in sync even when the dock is closed via titlebar
        action = self.view_actions.get(key)
        if action:
            prev = action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(prev)
        self._sync_view_actions()

    def _sync_action_state(self, action, visible: bool):
        prev = action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(prev)

    def _sync_view_actions(self):
        for key, action in self.view_actions.items():
            dock = self.docks.get(key)
            if not dock:
                continue
            prev = action.blockSignals(True)
            action.setChecked(dock.isVisible() or dock.isFloating())
            action.blockSignals(prev)

    def ensure_all_views_visible(self, force_unfloat: bool = False):
        for dock in self.docks.values():
            if force_unfloat and dock.isFloating():
                dock.setFloating(False)
            dock.setVisible(True)
            dock.show()
            dock.raise_()
        QApplication.processEvents()
        self._sync_view_actions()

    def _show_all_panels(self):
        # Force every dock visible and reapply canonical layout to surface missing panels
        self.apply_default_layout_all_views(save_as_default=False)
        self._remember_active_layout(self.saveGeometry(), self.saveState())

    def debug_dump_docks(self, tag: str = "dump"):
        lines = [f"Dock dump [{tag}]"]
        for name, dock in self.docks.items():
            geo = dock.geometry()
            tabbed = [d.objectName() for d in self.tabifiedDockWidgets(dock)]
            area = self.dockWidgetArea(dock)
            lines.append(
                f"{name}: title={dock.windowTitle()} visible={dock.isVisible()} floating={dock.isFloating()} "
                f"area={area} geom=({geo.x()},{geo.y()},{geo.width()},{geo.height()}) tabbed_with={tabbed}"
            )
        self._logger.info("\n".join(lines))
    def _sync_theme_actions(self):
        actions = getattr(self.topbar, "theme_actions", {})
        if not actions:
            return
        for name, action in actions.items():
            previous = action.blockSignals(True)
            action.setChecked(name == self.current_theme)
            action.blockSignals(previous)

    def closeEvent(self, event):
        self._remember_active_layout(self.saveGeometry(), self.saveState())
        self.data_engine.stop()
        super().closeEvent(event)

    def reset_layout(self):
        # Always reapply authoritative default layout to avoid restoring corrupted states
        self._apply_and_store_default()

    def save_layout_as_default(self):
        geom = self.saveGeometry()
        st = self.saveState()
        self._persist_default_layout(geom, st)
        self._remember_active_layout(geom, st)
        self._logger.info("Workspace saved as default layout")


_prev_qt_handler = None


def _qt_message_handler(mode, context, message):
    if "QGraphicsScene::addItem" in message:
        return
    if _prev_qt_handler:
        _prev_qt_handler(mode, context, message)
    else:
        try:
            sys.stderr.write(message + "\n")
        except Exception:
            pass


def run():
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "omniflow.log"
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handlers = [
        logging.StreamHandler(),
        RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8"),
    ]
    logging.basicConfig(level=logging.INFO, format=formatter._fmt, handlers=handlers, force=True)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("ui.panels.tape_panel").setLevel(logging.INFO)
    logging.getLogger("ui.panels.marketwatch_panel").setLevel(logging.INFO)
    logging.getLogger("core.data_engine.providers.binance_provider").setLevel(logging.INFO)
    global _prev_qt_handler
    if _prev_qt_handler is None:
        _prev_qt_handler = qInstallMessageHandler(_qt_message_handler)
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("OmniFlow Terminal Starting...")
    logger.info("=" * 80)
    
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    window.resize(1400, 900)
    app.exec()
