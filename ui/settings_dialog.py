from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    """
    Central app settings (MT5-style tabs).
    Currently wires Tape settings into QSettings; other tabs are placeholders.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(520, 420)

        self._tape_settings = QSettings("OmniFlow", "TapePanel")

        tabs = QTabWidget(self)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_tape_tab(), "Tape / Time & Sales")
        tabs.addTab(self._build_placeholder_tab("Chart / DOM / Footprint"), "Chart / DOM / Footprint")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # --------------------
    # Tabs
    # --------------------
    def _build_general_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QFormLayout(w)
        layout.addRow(QLabel("General settings coming soon."))
        return w

    def _build_placeholder_tab(self, text: str) -> QWidget:
        w = QWidget(self)
        layout = QFormLayout(w)
        layout.addRow(QLabel(f"{text} settings will be added later."))
        return w

    def _build_tape_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QFormLayout(w)
        layout.setLabelAlignment(Qt.AlignLeft)

        # Size mode default
        self.size_mode_combo = QComboBox(w)
        self.size_mode_combo.addItems(["BASE", "QUOTE", "COMPACT"])
        self.size_mode_combo.setCurrentText(str(self._tape_settings.value("size_mode", "QUOTE") or "QUOTE"))
        layout.addRow("Default Size Mode", self.size_mode_combo)

        # Filters (toggle defaults)
        self.aggr_only = QCheckBox(w)
        self.aggr_only.setChecked(bool(self._tape_settings.value("aggr_only", False)))
        layout.addRow("Aggressive Only (min notional)", self.aggr_only)

        self.blocks_only = QCheckBox(w)
        self.blocks_only.setChecked(self._as_bool(self._tape_settings.value("blocks_only", False)))
        layout.addRow("Block Trades Only", self.blocks_only)

        self.flags_enabled = QCheckBox(w)
        self.flags_enabled.setChecked(self._as_bool(self._tape_settings.value("flags_enabled", False)))
        layout.addRow("Enable Flags / Heuristics", self.flags_enabled)

        # Aggressive filter by notional
        self.min_notional = QDoubleSpinBox(w)
        self.min_notional.setRange(0, 1_000_000_000)
        self.min_notional.setDecimals(2)
        self.min_notional.setSingleStep(500)
        self.min_notional.setValue(float(self._tape_settings.value("min_notional_filter", 0.0)))
        layout.addRow("Min Notional (Aggressive filter)", self.min_notional)

        # Block threshold
        self.block_threshold = QDoubleSpinBox(w)
        self.block_threshold.setRange(0, 10_000_000_000)
        self.block_threshold.setDecimals(2)
        self.block_threshold.setSingleStep(10_000)
        self.block_threshold.setValue(float(self._tape_settings.value("block_threshold", 100_000.0)))
        layout.addRow("Block Threshold (USD)", self.block_threshold)

        # Sweep
        self.sweep_window = QSpinBox(w)
        self.sweep_window.setRange(10, 10_000)
        self.sweep_window.setValue(int(self._tape_settings.value("sweep_window_ms", 300)))
        layout.addRow("Sweep Window (ms)", self.sweep_window)

        self.sweep_levels = QSpinBox(w)
        self.sweep_levels.setRange(2, 50)
        self.sweep_levels.setValue(int(self._tape_settings.value("sweep_price_levels", 4)))
        layout.addRow("Sweep Price Levels >=", self.sweep_levels)

        self.sweep_min_notional = QDoubleSpinBox(w)
        self.sweep_min_notional.setRange(0, 1_000_000_000)
        self.sweep_min_notional.setDecimals(2)
        self.sweep_min_notional.setSingleStep(1000)
        self.sweep_min_notional.setValue(float(self._tape_settings.value("sweep_min_notional", 5_000.0)))
        layout.addRow("Sweep Notional ≥ (USD)", self.sweep_min_notional)

        self.sweep_min_price_diff = QDoubleSpinBox(w)
        self.sweep_min_price_diff.setRange(0, 1_000_000)
        self.sweep_min_price_diff.setDecimals(4)
        self.sweep_min_price_diff.setSingleStep(0.1)
        self.sweep_min_price_diff.setValue(float(self._tape_settings.value("sweep_min_price_diff", 1.0)))
        layout.addRow("Sweep Min Price Range", self.sweep_min_price_diff)

        # Iceberg
        self.iceberg_window = QSpinBox(w)
        self.iceberg_window.setRange(10, 10_000)
        self.iceberg_window.setValue(int(self._tape_settings.value("iceberg_window_ms", 400)))
        layout.addRow("Iceberg Window (ms)", self.iceberg_window)

        self.iceberg_count = QSpinBox(w)
        self.iceberg_count.setRange(2, 100)
        self.iceberg_count.setValue(int(self._tape_settings.value("iceberg_count", 5)))
        layout.addRow("Iceberg Repeats >=", self.iceberg_count)

        # Absorption
        self.absorb_window = QSpinBox(w)
        self.absorb_window.setRange(10, 10_000)
        self.absorb_window.setValue(int(self._tape_settings.value("absorb_window_ms", 800)))
        layout.addRow("Absorption Window (ms)", self.absorb_window)

        self.absorb_notional = QDoubleSpinBox(w)
        self.absorb_notional.setRange(0, 1_000_000_000)
        self.absorb_notional.setDecimals(2)
        self.absorb_notional.setSingleStep(1000)
        self.absorb_notional.setValue(float(self._tape_settings.value("absorb_volume", 20_000.0)))
        layout.addRow("Absorption Volume ≥ (USD)", self.absorb_notional)

        # Accumulation (to reduce noise)
        self.accumulation = QComboBox(w)
        self.accumulation.addItems(["Off", "2s", "5s", "10s", "15s", "30s", "60s"])
        current_ms = int(self._tape_settings.value("accumulation_interval_ms", 0))
        ms_to_opt = {0: "Off", 2000: "2s", 5000: "5s", 10000: "10s", 15000: "15s", 30000: "30s", 60000: "60s"}
        current_opt = ms_to_opt.get(current_ms, "Off")
        self.accumulation.setCurrentText(current_opt)
        layout.addRow("Accumulate trades every", self.accumulation)

        return w

    # --------------------
    # Save
    # --------------------
    def accept(self):
        # Tape settings
        self._tape_settings.setValue("size_mode", self.size_mode_combo.currentText())
        self._tape_settings.setValue("aggr_only", bool(self.aggr_only.isChecked()))
        self._tape_settings.setValue("blocks_only", bool(self.blocks_only.isChecked()))
        self._tape_settings.setValue("flags_enabled", bool(self.flags_enabled.isChecked()))
        self._tape_settings.setValue("min_notional_filter", float(self.min_notional.value()))
        self._tape_settings.setValue("block_threshold", float(self.block_threshold.value()))

        self._tape_settings.setValue("sweep_window_ms", int(self.sweep_window.value()))
        self._tape_settings.setValue("sweep_price_levels", int(self.sweep_levels.value()))
        self._tape_settings.setValue("sweep_min_notional", float(self.sweep_min_notional.value()))
        self._tape_settings.setValue("sweep_min_price_diff", float(self.sweep_min_price_diff.value()))

        self._tape_settings.setValue("iceberg_window_ms", int(self.iceberg_window.value()))
        self._tape_settings.setValue("iceberg_count", int(self.iceberg_count.value()))

        self._tape_settings.setValue("absorb_window_ms", int(self.absorb_window.value()))
        self._tape_settings.setValue("absorb_volume", float(self.absorb_notional.value()))

        opt_to_ms = {
            "Off": 0,
            "2s": 2000,
            "5s": 5000,
            "10s": 10000,
            "15s": 15000,
            "30s": 30000,
            "60s": 60000,
        }
        self._tape_settings.setValue("accumulation_interval_ms", opt_to_ms.get(self.accumulation.currentText(), 0))

        super().accept()

    def _as_bool(self, val) -> bool:
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        if isinstance(val, (int, float)):
            return val != 0
        s = str(val).strip().lower()
        return s in ("1", "true", "yes", "on")
