# Biblioteca padrão do Python
# random → usado para simular valores de CPU e MEM
# time   → usado para mostrar a hora da última atualização
import random
import time


# =========================
# IMPORTS DO QT (PySide6)
# =========================

# QTimer → temporizador para atualizar métricas periodicamente
from PySide6.QtCore import QTimer

# QLabel → texto simples
# QStatusBar → barra de estado inferior da janela
from PySide6.QtWidgets import QLabel, QStatusBar


# =========================
# TEMA DA APLICAÇÃO
# =========================

# Cores e tipografia centralizadas
from ui.theme import colors, typography


# ==========================================================
# CLASSE: StatusBar
# ==========================================================
# Representa a barra de estado INFERIOR da aplicação.
#
# Funções desta barra:
# - Mostrar provider de dados (ex: Binance WS)
# - Mostrar CPU e MEM
# - Indicar estado do stream de mercado
# - Mostrar hora da última atualização
# - Indicar estado da ligação (Connected / Disconnected)
# ==========================================================
class StatusBar(QStatusBar):

    def __init__(self, parent=None):
        # Inicializa a classe base QStatusBar
        super().__init__(parent)

        # Nome interno do widget (útil para estilos e debug)
        self.setObjectName("StatusBar")

        # Pequeno padding interno da status bar
        self.setStyleSheet("QStatusBar{padding:4px;}")


        # ==================================================
        # LABELS FIXOS DA STATUS BAR
        # ==================================================

        # Nome do provider de dados (simulado)
        self.provider_label = QLabel("Binance WS")

        # Uso de CPU (simulado)
        self.cpu_label = QLabel("CPU: --%")

        # Uso de memória (simulado)
        self.mem_label = QLabel("MEM: --%")

        # Estado do stream de dados
        self.stream_label = QLabel("Market data streaming")

        # Hora da última atualização
        self.update_label = QLabel("Last update: --:--:--")


        # ==================================================
        # ESTILO E ADIÇÃO DOS LABELS FIXOS
        # ==================================================
        # addPermanentWidget → widgets ficam sempre visíveis,
        # alinhados à direita da StatusBar
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


        # ==================================================
        # LABEL DE CONEXÃO (DINÂMICO)
        # ==================================================

        # Estado da ligação (fica à esquerda)
        self.connection_label = QLabel("Connected")
        self.connection_label.setFont(typography.inter(11))
        self.connection_label.setStyleSheet(
            f"color: {colors.ACCENT_GREEN};"
        )

        # addWidget → widget normal (lado esquerdo da StatusBar)
        self.addWidget(self.connection_label)


        # ==================================================
        # TIMER DE ATUALIZAÇÃO
        # ==================================================
        # Atualiza CPU, MEM e hora a cada 1.5 segundos
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_metrics)
        self.timer.start(1500)


    # ==================================================
    # ATUALIZAÇÃO DE MÉTRICAS (SIMULADAS)
    # ==================================================
    def _update_metrics(self):
        # Valores simulados
        cpu = random.randint(30, 60)
        mem = random.randint(40, 75)

        # Hora atual
        now = time.strftime("%H:%M:%S")

        # Atualiza textos dos labels
        self.cpu_label.setText(f"CPU: {cpu}%")
        self.mem_label.setText(f"MEM: {mem}%")
        self.update_label.setText(f"Last update: {now}")


    # ==================================================
    # UPDATE DE DADOS REAIS (FUTURO)
    # ==================================================
    def update_data(self, data):
        # Função reservada para integração futura:
        # - CPU real
        # - memória real
        # - estado real do feed
        pass


    # ==================================================
    # REFRESH DE ESTILOS (THEME SWITCH)
    # ==================================================
    def refresh_styles(self):
        # Reaplica estilos quando o tema muda
        for lbl in [
            self.provider_label,
            self.cpu_label,
            self.mem_label,
            self.stream_label,
            self.update_label,
        ]:
            lbl.setStyleSheet(f"color: {colors.MUTED};")

        self.connection_label.setStyleSheet(
            f"color: {colors.ACCENT_GREEN};"
        )
