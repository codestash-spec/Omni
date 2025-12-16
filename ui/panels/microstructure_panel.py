# ==========================================================
# IMPORTS STANDARD
# ==========================================================

import random
import logging

# ==========================================================
# IMPORTS NUMÉRICOS / GRÁFICOS
# ==========================================================

import numpy as np
import pyqtgraph as pg

# ==========================================================
# IMPORTS QT
# ==========================================================

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

# ==========================================================
# TEMA E EVENTOS DO CORE
# ==========================================================

from ui.theme import colors, typography
from core.data_engine.events import TradeEvent, CandleUpdate


# ==========================================================
# MICROSTRUCTURE PANEL
# ==========================================================

class MicrostructurePanel(QWidget):
    """
    Painel de Microestrutura de Mercado.

    Objetivo:
    - Visualizar métricas de order flow
    - Ajudar a identificar regime de mercado

    Métricas representadas:
    - Cumulative Delta
    - OFI (Order Flow Imbalance)
    - VPIN (proxy simplificada)

    Estado atual:
    - Dados fictícios (dummy)
    - Estrutura pronta para dados reais
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Nome do widget (docks / estilos)
        self.setObjectName("MicrostructurePanel")

        # Logger local
        self._logger = logging.getLogger(__name__)

        # Métricas internas (estado)
        self._cum_delta = 0.0
        self._ofi = 0.0
        self._vpin = 50

        # ==================================================
        # TIMER DE REFRESH (dummy data)
        # ==================================================

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(500)  # 2 Hz
        self._refresh_timer.timeout.connect(self._refresh_dummy_data)


        # ==================================================
        # HEADER
        # ==================================================

        header = QHBoxLayout()

        lbl = QLabel("Microstructure")
        lbl.setFont(typography.inter(11))
        header.addWidget(lbl)

        header.addStretch()

        # Label de regime de mercado (dummy)
        self.regime = QLabel("Regime: TRENDING")
        self.regime.setStyleSheet(f"color:{colors.ACCENT_GREEN};")
        header.addWidget(self.regime)


        # ==================================================
        # CUMULATIVE DELTA PLOT
        # ==================================================

        self.cum_delta_plot = pg.PlotWidget()
        self.cum_delta_plot.showGrid(x=True, y=True, alpha=0.2)
        self.cum_delta_plot.setLabel("left", "Cumulative Delta")
        self.cum_delta_plot.getPlotItem().hideButtons()


        # ==================================================
        # OFI PLOT
        # ==================================================

        self.ofi_plot = pg.PlotWidget()
        self.ofi_plot.showGrid(x=True, y=True, alpha=0.2)
        self.ofi_plot.setLabel("left", "Order Flow Imbalance (OFI)")
        self.ofi_plot.getPlotItem().hideButtons()


        # ==================================================
        # VPIN (BARRA DE PROGRESSO)
        # ==================================================

        self.vpin = QProgressBar()
        self.vpin.setRange(0, 100)
        self.vpin.setValue(49)
        self.vpin.setFormat(
            "VPIN (Volume-Synchronized Probability of Informed Trading) %p%"
        )


        # ==================================================
        # LAYOUT PRINCIPAL
        # ==================================================

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addLayout(header)
        layout.addWidget(self.cum_delta_plot, stretch=1)
        layout.addWidget(self.ofi_plot, stretch=1)
        layout.addWidget(self.vpin)


        # ==================================================
        # INIT
        # ==================================================

        self._populate()          # dados iniciais fictícios
        self._wire_engine()       # tentativa de ligação ao CoreDataEngine
        self._refresh_timer.start()


    # ======================================================
    # POPULAÇÃO INICIAL (DUMMY)
    # ======================================================

    def _populate(self):
        """
        Preenche os gráficos com dados fictícios.
        Usado apenas para:
        - validar layout
        - testar performance gráfica
        """
        x = np.arange(80)

        cum_delta = np.cumsum(np.random.normal(0, 3, size=len(x)))
        ofi = np.cumsum(np.random.normal(0, 2, size=len(x)))

        self.cum_delta_plot.plot(
            x,
            cum_delta,
            pen=pg.mkPen(colors.ACCENT_BLUE, width=2),
        )

        self.ofi_plot.plot(
            x,
            ofi,
            pen=pg.mkPen(colors.ACCENT_GREEN, width=2),
        )


    # ======================================================
    # REFRESH DE DADOS FICTÍCIOS
    # ======================================================

    def _refresh_dummy_data(self):
        """
        Atualiza métricas com ruído aleatório.

        NOTA:
        - Este método será removido quando dados reais entrarem.
        """
        self._cum_delta += np.random.normal(0, 3)
        self._ofi += np.random.normal(0, 2)
        self._vpin = max(0, min(100, self._vpin + np.random.uniform(-5, 5)))
        self.vpin.setValue(int(self._vpin))


    # ======================================================
    # LIGAÇÃO AO CORE DATA ENGINE
    # ======================================================

    def _wire_engine(self, attempts=0):
        """
        Liga o painel ao CoreDataEngine quando disponível.
        Usa retry para evitar race conditions na inicialização.
        """
        window = self.window()
        engine = getattr(window, "data_engine", None) if window else None

        if engine:
            try:
                engine.trade.connect(self._on_trade)
                engine.candle_update.connect(self._on_candle_update)
                self._logger.info("MicrostructurePanel wired to CoreDataEngine")
            except Exception as e:
                self._logger.warning("MicrostructurePanel wire failed: %s", e)
        elif attempts < 3:
            QTimer.singleShot(
                200,
                lambda: self._wire_engine(attempts + 1),
            )


    # ======================================================
    # EVENT HANDLERS (DADOS REAIS – FUTURO)
    # ======================================================

    def _on_trade(self, evt: TradeEvent):
        """
        Handler de trades reais.
        Aqui será calculado:
        - delta por agressão
        - impacto de volume
        """
        pass

    def _on_candle_update(self, evt: CandleUpdate):
        """
        Handler de candles reais.
        Aqui será calculado:
        - OFI
        - regime de mercado
        """
        pass


    # ======================================================
    # API PÚBLICA
    # ======================================================

    def update_data(self, micro_data):
        """
        Hook genérico para updates externos.
        """
        self.cum_delta_plot.clear()
        self.ofi_plot.clear()
        self._populate()
