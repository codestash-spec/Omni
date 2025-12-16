# Biblioteca padrão do Python usada aqui apenas para gerar valores aleatórios
# (latência e FPS simulados)
import random


# =========================
# IMPORTS DO QT (PySide6)
# =========================

# Qt → enums e flags (alinhamentos, áreas, etc.)
# QTimer → temporizador para atualizar métricas periodicamente
from PySide6.QtCore import Qt, QTimer

# QFont → configuração de fontes
# QAction → ações usadas em menus (File, View, Tools, etc.)
from PySide6.QtGui import QFont, QAction

# Widgets básicos usados na TopBar
from PySide6.QtWidgets import (
    QComboBox,     # Dropdown (Asset Class)
    QHBoxLayout,   # Layout horizontal
    QLabel,        # Texto
    QWidget,       # Base para qualquer componente visual
)

# Tema da aplicação (cores e tipografia centralizadas)
from ui.theme import colors, typography


# ==========================================================
# CLASSE: TopBar
# ==========================================================
# Esta classe representa a barra superior da aplicação,
# logo ABAIXO do menu principal.
#
# Funções desta barra:
# - Mostrar o nome da aplicação
# - Selecionar a Asset Class
# - Indicar modo SIM / LIVE
# - Mostrar latência, FPS e estado da ligação
# ==========================================================
class TopBar(QWidget):
    """Barra de informação ABAIXO do menu"""

    def __init__(self, parent=None):
        # Inicializa o QWidget base
        super().__init__(parent)

        # Nome interno do widget (útil para estilos e debug)
        self.setObjectName("TopBar")

        # Altura fixa da TopBar
        self.setFixedHeight(40)


        # ==================================================
        # WIDGETS VISUAIS
        # ==================================================

        # Título principal da aplicação
        self.title_label = QLabel("OmniFlow Terminal")
        self.title_label.setFont(
            typography.inter(16, QFont.DemiBold)
        )
        self.title_label.setStyleSheet(
            f"color: {colors.TEXT};"
        )

        # Label "Asset Class:"
        self.asset_label = QLabel("Asset Class:")
        self.asset_label.setFont(
            typography.inter(11, QFont.DemiBold)
        )
        self.asset_label.setStyleSheet(
            f"color: {colors.MUTED};"
        )

        # Dropdown para escolher a classe de ativos
        self.asset_class_combo = QComboBox()
        self.asset_class_combo.addItems(
            ["Crypto", "Futures", "Forex", "Equities"]
        )
        self.asset_class_combo.setCurrentText("Crypto")
        self.asset_class_combo.setFixedWidth(130)

        # Badge "SIM" (simulação)
        self.sim_badge = QLabel("SIM")
        self.sim_badge.setFont(
            typography.inter(11, QFont.DemiBold)
        )
        self.sim_badge.setAlignment(Qt.AlignCenter)
        self.sim_badge.setFixedWidth(48)
        self.sim_badge.setStyleSheet(
            f"""
            color: {colors.BACKGROUND};
            background: {colors.HIGHLIGHT};
            border-radius: 4px;
            padding: 2px 6px;
            """
        )

        # Labels de métricas (latência e FPS)
        self.latency_label = QLabel("Latency: --ms")
        self.fps_label = QLabel("FPS: --")

        # Estilo comum para métricas técnicas
        for lbl in (self.latency_label, self.fps_label):
            lbl.setFont(
                typography.mono(11, QFont.DemiBold)
            )
            lbl.setStyleSheet(
                f"color: {colors.MUTED};"
            )

        # Label de estado da ligação
        self.connection_label = QLabel("Connected")
        self.connection_label.setFont(
            typography.inter(12, QFont.DemiBold)
        )
        self.connection_label.setStyleSheet(
            f"color: {colors.ACCENT_GREEN};"
        )
        self.connection_label.setContentsMargins(4, 0, 0, 0)


        # ==================================================
        # LAYOUT HORIZONTAL
        # ==================================================
        # Organiza todos os widgets da esquerda para a direita
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        layout.addWidget(self.title_label)
        layout.addSpacing(12)
        layout.addWidget(self.asset_label)
        layout.addWidget(self.asset_class_combo)
        layout.addSpacing(8)
        layout.addWidget(self.sim_badge)

        # Espaço elástico → empurra métricas para a direita
        layout.addStretch()

        layout.addWidget(self.latency_label)
        layout.addWidget(self.fps_label)
        layout.addSpacing(8)
        layout.addWidget(self.connection_label)


        # ==================================================
        # ACTIONS (MENUS)
        # ==================================================
        # Estas ações são usadas pelos menus da MainWindow

        self.file_actions = {
            "new_workspace": QAction("New Workspace", self),
            "open_workspace": QAction("Open Workspace", self),
            "save_workspace": QAction("Save Workspace", self),
            "save_workspace_as": QAction("Save Workspace As…", self),
            "exit": QAction("Exit", self),
        }

        # Menus ainda não ligados (reservados)
        self.view_menu = None
        self.view_actions = {}
        self.theme_actions = {}

        self.tools_actions = {
            "settings": QAction("Settings", self),
            "layout_manager": QAction("Layout Manager", self),
            "layout_debug": QAction("Layout Debug -> Dump Now", self),
        }


        # ==================================================
        # TIMER DE MÉTRICAS
        # ==================================================
        # Atualiza latência e FPS a cada 1 segundo
        self.metric_timer = QTimer(self)
        self.metric_timer.timeout.connect(self._update_metrics)
        self.metric_timer.start(1000)


    # ==================================================
    # MÉTRICAS (SIMULADAS)
    # ==================================================
    def _update_metrics(self):
        # Valores simulados (placeholder)
        latency = random.randint(8, 24)
        fps = random.choice([58, 59, 60, 61])

        # Atualiza os textos
        self.latency_label.setText(f"Latency: {latency}ms")
        self.fps_label.setText(f"FPS: {fps}")


    # ==================================================
    # UPDATE DE DADOS (FUTURO)
    # ==================================================
    def update_data(self, data):
        # Função preparada para receber dados reais no futuro
        # Ex: estado da ligação, latência real, broker, etc.
        pass


    # ==================================================
    # REFRESH DE ESTILOS (THEME SWITCH)
    # ==================================================
    def refresh_styles(self):
        # Reaplica cores quando o tema muda
        self.title_label.setStyleSheet(f"color: {colors.TEXT};")
        self.asset_label.setStyleSheet(f"color: {colors.MUTED};")

        self.sim_badge.setStyleSheet(
            f"""
            color: {colors.BACKGROUND};
            background: {colors.HIGHLIGHT};
            border-radius: 4px;
            padding: 2px 6px;
            """
        )

        for lbl in (self.latency_label, self.fps_label):
            lbl.setStyleSheet(f"color: {colors.MUTED};")

        self.connection_label.setStyleSheet(
            f"color: {colors.ACCENT_GREEN};"
        )
