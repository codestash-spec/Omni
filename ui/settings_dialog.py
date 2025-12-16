# ==========================================================
# IMPORTS DO QT
# ==========================================================

# Qt → alinhamentos e enums
# QSettings → sistema nativo de settings persistentes (registry no Windows)
from PySide6.QtCore import Qt, QSettings

# Widgets usados no diálogo de Settings
from PySide6.QtWidgets import (
    QCheckBox,         # Checkbox (on/off)
    QComboBox,         # Dropdown
    QDialog,           # Janela modal
    QDialogButtonBox,  # Botões OK / Cancel
    QDoubleSpinBox,    # Campo numérico decimal
    QFormLayout,       # Layout label → campo
    QLabel,            # Texto
    QSpinBox,          # Campo numérico inteiro
    QTabWidget,        # Abas (tabs)
    QVBoxLayout,       # Layout vertical
    QWidget,           # Base de qualquer widget
)


# ==========================================================
# CLASSE: SettingsDialog
# ==========================================================
# Esta classe define a janela de DEFINIÇÕES da aplicação,
# no estilo MT5 / Bloomberg:
# - Abas (tabs)
# - Settings persistentes
# - Tape / Time & Sales configurável
#
# NOTA:
# - Só o Tape está ligado a settings reais
# - Os outros tabs são placeholders
# ==========================================================
class SettingsDialog(QDialog):
    """
    Central app settings (MT5-style tabs).
    Currently wires Tape settings into QSettings; other tabs are placeholders.
    """

    def __init__(self, parent=None):
        # Inicializa o QDialog base
        super().__init__(parent)

        # Título da janela
        self.setWindowTitle("Settings")

        # Torna a janela MODAL (bloqueia a app enquanto está aberta)
        self.setModal(True)

        # Tamanho inicial da janela
        self.resize(520, 420)


        # ==================================================
        # QSETTINGS — STORAGE PERSISTENTE
        # ==================================================
        # Isto guarda settings automaticamente:
        # - Windows → Registry
        # - Linux/macOS → ficheiros de config
        #
        # Namespace:
        #   Empresa: OmniFlow
        #   App: TapePanel
        self._tape_settings = QSettings("OmniFlow", "TapePanel")


        # ==================================================
        # TABS (ABAS)
        # ==================================================
        tabs = QTabWidget(self)

        # Aba General (placeholder)
        tabs.addTab(
            self._build_general_tab(),
            "General"
        )

        # Aba Tape / Time & Sales (REAL)
        tabs.addTab(
            self._build_tape_tab(),
            "Tape / Time & Sales"
        )

        # Aba futura (placeholder)
        tabs.addTab(
            self._build_placeholder_tab("Chart / DOM / Footprint"),
            "Chart / DOM / Footprint"
        )


        # ==================================================
        # BOTÕES OK / CANCEL
        # ==================================================
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok |
            QDialogButtonBox.Cancel
        )

        # OK → guarda settings
        buttons.accepted.connect(self.accept)

        # Cancel → fecha sem guardar
        buttons.rejected.connect(self.reject)


        # ==================================================
        # LAYOUT PRINCIPAL
        # ==================================================
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)


    # ======================================================
    # CONSTRUÇÃO DOS TABS
    # ======================================================

    def _build_general_tab(self) -> QWidget:
        """
        Aba General (placeholder)
        """
        w = QWidget(self)
        layout = QFormLayout(w)
        layout.addRow(QLabel("General settings coming soon."))
        return w


    def _build_placeholder_tab(self, text: str) -> QWidget:
        """
        Aba genérica placeholder
        """
        w = QWidget(self)
        layout = QFormLayout(w)
        layout.addRow(QLabel(f"{text} settings will be added later."))
        return w


    # ======================================================
    # TAPE / TIME & SALES TAB (A PARTE SÉRIA)
    # ======================================================
    def _build_tape_tab(self) -> QWidget:
        """
        Aba de configurações do Tape (Time & Sales)
        """
        w = QWidget(self)
        layout = QFormLayout(w)

        # Alinhamento dos labels
        layout.setLabelAlignment(Qt.AlignLeft)


        # --------------------------------------------------
        # SIZE MODE (BASE / QUOTE / COMPACT)
        # --------------------------------------------------
        self.size_mode_combo = QComboBox(w)
        self.size_mode_combo.addItems(["BASE", "QUOTE", "COMPACT"])

        # Carrega valor guardado ou usa QUOTE como default
        self.size_mode_combo.setCurrentText(
            str(self._tape_settings.value("size_mode", "QUOTE") or "QUOTE")
        )

        layout.addRow("Default Size Mode", self.size_mode_combo)


        # --------------------------------------------------
        # FILTROS (CHECKBOXES)
        # --------------------------------------------------

        # Aggressive trades only
        self.aggr_only = QCheckBox(w)
        self.aggr_only.setChecked(
            bool(self._tape_settings.value("aggr_only", False))
        )
        layout.addRow("Aggressive Only (min notional)", self.aggr_only)

        # Block trades only
        self.blocks_only = QCheckBox(w)
        self.blocks_only.setChecked(
            self._as_bool(self._tape_settings.value("blocks_only", False))
        )
        layout.addRow("Block Trades Only", self.blocks_only)

        # Flags / heurísticas (sweep, iceberg, absorption)
        self.flags_enabled = QCheckBox(w)
        self.flags_enabled.setChecked(
            self._as_bool(self._tape_settings.value("flags_enabled", False))
        )
        layout.addRow("Enable Flags / Heuristics", self.flags_enabled)


        # --------------------------------------------------
        # AGGRESSIVE FILTER (MIN NOTIONAL)
        # --------------------------------------------------
        self.min_notional = QDoubleSpinBox(w)
        self.min_notional.setRange(0, 1_000_000_000)
        self.min_notional.setDecimals(2)
        self.min_notional.setSingleStep(500)
        self.min_notional.setValue(
            float(self._tape_settings.value("min_notional_filter", 0.0))
        )
        layout.addRow("Min Notional (Aggressive filter)", self.min_notional)


        # --------------------------------------------------
        # BLOCK TRADES
        # --------------------------------------------------
        self.block_threshold = QDoubleSpinBox(w)
        self.block_threshold.setRange(0, 10_000_000_000)
        self.block_threshold.setDecimals(2)
        self.block_threshold.setSingleStep(10_000)
        self.block_threshold.setValue(
            float(self._tape_settings.value("block_threshold", 100_000.0))
        )
        layout.addRow("Block Threshold (USD)", self.block_threshold)


        # --------------------------------------------------
        # SWEEP DETECTION
        # --------------------------------------------------
        self.sweep_window = QSpinBox(w)
        self.sweep_window.setRange(10, 10_000)
        self.sweep_window.setValue(
            int(self._tape_settings.value("sweep_window_ms", 300))
        )
        layout.addRow("Sweep Window (ms)", self.sweep_window)

        self.sweep_levels = QSpinBox(w)
        self.sweep_levels.setRange(2, 50)
        self.sweep_levels.setValue(
            int(self._tape_settings.value("sweep_price_levels", 4))
        )
        layout.addRow("Sweep Price Levels >=", self.sweep_levels)

        self.sweep_min_notional = QDoubleSpinBox(w)
        self.sweep_min_notional.setRange(0, 1_000_000_000)
        self.sweep_min_notional.setDecimals(2)
        self.sweep_min_notional.setSingleStep(1000)
        self.sweep_min_notional.setValue(
            float(self._tape_settings.value("sweep_min_notional", 5_000.0))
        )
        layout.addRow("Sweep Notional ≥ (USD)", self.sweep_min_notional)

        self.sweep_min_price_diff = QDoubleSpinBox(w)
        self.sweep_min_price_diff.setRange(0, 1_000_000)
        self.sweep_min_price_diff.setDecimals(4)
        self.sweep_min_price_diff.setSingleStep(0.1)
        self.sweep_min_price_diff.setValue(
            float(self._tape_settings.value("sweep_min_price_diff", 1.0))
        )
        layout.addRow("Sweep Min Price Range", self.sweep_min_price_diff)


        # --------------------------------------------------
        # ICEBERG DETECTION
        # --------------------------------------------------
        self.iceberg_window = QSpinBox(w)
        self.iceberg_window.setRange(10, 10_000)
        self.iceberg_window.setValue(
            int(self._tape_settings.value("iceberg_window_ms", 400))
        )
        layout.addRow("Iceberg Window (ms)", self.iceberg_window)

        self.iceberg_count = QSpinBox(w)
        self.iceberg_count.setRange(2, 100)
        self.iceberg_count.setValue(
            int(self._tape_settings.value("iceberg_count", 5))
        )
        layout.addRow("Iceberg Repeats >=", self.iceberg_count)


        # --------------------------------------------------
        # ABSORPTION DETECTION
        # --------------------------------------------------
        self.absorb_window = QSpinBox(w)
        self.absorb_window.setRange(10, 10_000)
        self.absorb_window.setValue(
            int(self._tape_settings.value("absorb_window_ms", 800))
        )
        layout.addRow("Absorption Window (ms)", self.absorb_window)

        self.absorb_notional = QDoubleSpinBox(w)
        self.absorb_notional.setRange(0, 1_000_000_000)
        self.absorb_notional.setDecimals(2)
        self.absorb_notional.setSingleStep(1000)
        self.absorb_notional.setValue(
            float(self._tape_settings.value("absorb_volume", 20_000.0))
        )
        layout.addRow("Absorption Volume ≥ (USD)", self.absorb_notional)


        # --------------------------------------------------
        # ACCUMULATION (REDUÇÃO DE RUÍDO)
        # --------------------------------------------------
        self.accumulation = QComboBox(w)
        self.accumulation.addItems(
            ["Off", "2s", "5s", "10s", "15s", "30s", "60s"]
        )

        current_ms = int(
            self._tape_settings.value("accumulation_interval_ms", 0)
        )

        ms_to_opt = {
            0: "Off",
            2000: "2s",
            5000: "5s",
            10000: "10s",
            15000: "15s",
            30000: "30s",
            60000: "60s",
        }

        self.accumulation.setCurrentText(
            ms_to_opt.get(current_ms, "Off")
        )

        layout.addRow("Accumulate trades every", self.accumulation)

        return w


    # ======================================================
    # GUARDAR SETTINGS (OK)
    # ======================================================
    def accept(self):
        """
        Guarda todas as definições do Tape em QSettings
        """

        self._tape_settings.setValue(
            "size_mode", self.size_mode_combo.currentText()
        )
        self._tape_settings.setValue(
            "aggr_only", bool(self.aggr_only.isChecked())
        )
        self._tape_settings.setValue(
            "blocks_only", bool(self.blocks_only.isChecked())
        )
        self._tape_settings.setValue(
            "flags_enabled", bool(self.flags_enabled.isChecked())
        )
        self._tape_settings.setValue(
            "min_notional_filter", float(self.min_notional.value())
        )
        self._tape_settings.setValue(
            "block_threshold", float(self.block_threshold.value())
        )

        self._tape_settings.setValue(
            "sweep_window_ms", int(self.sweep_window.value())
        )
        self._tape_settings.setValue(
            "sweep_price_levels", int(self.sweep_levels.value())
        )
        self._tape_settings.setValue(
            "sweep_min_notional", float(self.sweep_min_notional.value())
        )
        self._tape_settings.setValue(
            "sweep_min_price_diff", float(self.sweep_min_price_diff.value())
        )

        self._tape_settings.setValue(
            "iceberg_window_ms", int(self.iceberg_window.value())
        )
        self._tape_settings.setValue(
            "iceberg_count", int(self.iceberg_count.value())
        )

        self._tape_settings.setValue(
            "absorb_window_ms", int(self.absorb_window.value())
        )
        self._tape_settings.setValue(
            "absorb_volume", float(self.absorb_notional.value())
        )

        opt_to_ms = {
            "Off": 0,
            "2s": 2000,
            "5s": 5000,
            "10s": 10000,
            "15s": 15000,
            "30s": 30000,
            "60s": 60000,
        }

        self._tape_settings.setValue(
            "accumulation_interval_ms",
            opt_to_ms.get(self.accumulation.currentText(), 0)
        )

        # Chama o accept original do QDialog (fecha a janela)
        super().accept()


    # ======================================================
    # NORMALIZAÇÃO DE BOOLEANOS
    # ======================================================
    def _as_bool(self, val) -> bool:
        """
        Converte valores estranhos de QSettings em booleano real
        """
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        if isinstance(val, (int, float)):
            return val != 0
        s = str(val).strip().lower()
        return s in ("1", "true", "yes", "on")
