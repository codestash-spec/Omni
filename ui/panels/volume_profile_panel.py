# ==========================================================
# IMPORTS BÁSICOS
# ==========================================================

import logging

# defaultdict → facilita acumular volumes por preço
# deque → fila eficiente para trades (FIFO com limite)
from collections import defaultdict, deque

# dataclass → estrutura de dados simples
from dataclasses import dataclass

# Tipagem (não afeta execução, só clareza)
from typing import Deque, Dict, List, Tuple, Optional


# ==========================================================
# IMPORTS QT (GRÁFICOS)
# ==========================================================

from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QTimer, Qt


# ==========================================================
# EVENTS E MODELOS DO CORE
# ==========================================================

from core.data_engine.events import (
    TradeEvent,
    CandleHistory,
    CandleUpdate,
    TimeframeChanged,
    SymbolChanged,
)

from core.data_engine.models import Trade, Candle


# ==========================================================
# TEMA DA UI
# ==========================================================

from ui.theme import colors, typography


# ==========================================================
# DATA CLASS — BALDE DE VOLUME POR PREÇO
# ==========================================================

@dataclass
class ProfileBucket:
    """
    Representa um nível de preço no Volume Profile
    """
    price: float
    volume: float


# ==========================================================
# AGREGADOR DE VOLUME PROFILE (LÓGICA)
# ==========================================================

class VolumeProfileAggregator:
    """
    Responsável por:
    - acumular trades
    - acumular candles
    - calcular POC, VAH, VAL
    - devolver buckets prontos para desenhar
    """

    def __init__(self):
        # Trades recentes (máx 8000)
        self.trades: Deque[Trade] = deque(maxlen=8000)

        # Candles do timeframe atual
        self.candles: List[Candle] = []

        # Timeframe em ms (default 1m)
        self.timeframe_ms = 60_000

        # Símbolo atual
        self.symbol = "BTCUSDT"

        # Janela de cálculo (nº de candles)
        self.window_candles = 120


    # ------------------------------------------------------
    # ALTERAÇÃO DE SÍMBOLO
    # ------------------------------------------------------
    def set_symbol(self, symbol: str):
        self.symbol = symbol.upper()
        self.trades.clear()
        self.candles.clear()


    # ------------------------------------------------------
    # ALTERAÇÃO DE TIMEFRAME
    # ------------------------------------------------------
    def set_timeframe(self, tf: str):
        mapping = {
            "1m": 60_000,
            "5m": 300_000,
            "15m": 900_000,
            "1h": 3_600_000,
            "4h": 14_400_000,
            "1d": 86_400_000,
        }
        self.timeframe_ms = mapping.get(tf.lower(), 60_000)
        self.trades.clear()
        self.candles.clear()


    # ------------------------------------------------------
    # HISTÓRICO DE CANDLES
    # ------------------------------------------------------
    def add_candles(self, candles: List[Candle]):
        # Guarda apenas a janela relevante
        self.candles = list(candles)[-self.window_candles :]


    def add_candle_update(self, candle: Candle, closed: bool):
        # Só adiciona candle fechado
        if not closed:
            return
        self.candles.append(candle)
        self.candles = self.candles[-self.window_candles :]


    # ------------------------------------------------------
    # TRADES
    # ------------------------------------------------------
    def add_trade(self, trade: Trade):
        # Ignora trades de outro símbolo
        if trade.symbol.upper() != self.symbol:
            return
        self.trades.append(trade)


    # ------------------------------------------------------
    # INÍCIO DA JANELA TEMPORAL
    # ------------------------------------------------------
    def _window_start_ms(self) -> Optional[int]:
        if not self.candles:
            return None
        return (
            self.candles[-1].open_time
            - self.timeframe_ms * (self.window_candles - 1)
        )


    # ------------------------------------------------------
    # CÁLCULO DO VOLUME PROFILE
    # ------------------------------------------------------
    def profile(
        self,
    ) -> Tuple[List[ProfileBucket], Optional[float], Optional[float], Optional[float]]:
        """
        Retorna:
        - lista de buckets (preço, volume)
        - POC
        - VAH
        - VAL
        """

        start_ms = self._window_start_ms()
        buckets: Dict[float, float] = defaultdict(float)

        # Remove trades fora da janela temporal
        if start_ms is not None:
            cutoff = start_ms
            while self.trades and self.trades[0].ts < cutoff:
                self.trades.popleft()

        # Agregação por preço (arredondado)
        for t in self.trades:
            price = round(t.price, 2)
            buckets[price] += t.qty

        # Fallback: usar volume dos candles se não houver trades
        if not buckets and self.candles:
            for c in self.candles:
                buckets[round(c.close, 2)] += c.volume

        # Criar buckets válidos
        items = [
            ProfileBucket(price=p, volume=v)
            for p, v in buckets.items()
            if v > 1e-6
        ]

        if not items:
            return [], None, None, None

        # Ordenar por preço
        items.sort(key=lambda b: b.price)

        total_vol = sum(b.volume for b in items)

        # POC = preço com maior volume
        poc_price = max(items, key=lambda b: b.volume).price

        # ------------------------------
        # VALUE AREA (70%)
        # ------------------------------
        sorted_by_vol = sorted(items, key=lambda b: b.volume, reverse=True)
        acc = 0.0
        selected_prices = set()

        for b in sorted_by_vol:
            acc += b.volume
            selected_prices.add(b.price)
            if acc >= total_vol * 0.7:
                break

        vah = max(selected_prices) if selected_prices else None
        val = min(selected_prices) if selected_prices else None

        # Limitar a 80 níveis para evitar scroll gigante
        limited = sorted_by_vol[:80]
        limited.sort(key=lambda b: b.price, reverse=True)

        return limited, poc_price, vah, val


# ==========================================================
# VIEW — DESENHO DO VOLUME PROFILE
# ==========================================================

class VolumeProfileView(QGraphicsView):
    """
    Responsável APENAS por desenhar o Volume Profile
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Anti-aliasing para melhor visual
        self.setRenderHint(QPainter.Antialiasing, True)

        # Cena gráfica
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # Alinhamento
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # Altura de cada linha
        self.row_height = 22


    def populate(
        self,
        buckets: List[ProfileBucket],
        poc: Optional[float],
        vah: Optional[float],
        val: Optional[float],
    ):
        """
        Desenha todos os níveis do Volume Profile
        """

        self.scene.clear()

        max_vol = max(b.volume for b in buckets) if buckets else 1
        width_max = 220
        x_origin = 80
        font = typography.mono(10)

        # Ordenar de cima para baixo (preço alto → baixo)
        buckets_sorted = sorted(buckets, key=lambda b: b.price, reverse=True)

        for i, bucket in enumerate(buckets_sorted):
            y = i * self.row_height

            # Largura proporcional ao volume
            bar_width = width_max * bucket.volume / max_vol if max_vol else 0

            # Cor por defeito
            color = colors.ACCENT_BLUE

            # POC destacado
            if poc is not None and abs(bucket.price - poc) < 1e-6:
                color = colors.HIGHLIGHT

            # Value Area
            elif val is not None and vah is not None and val <= bucket.price <= vah:
                color = colors.ACCENT_BLUE

            # Barra de volume
            rect = QGraphicsRectItem(
                x_origin,
                y + 4,
                bar_width,
                self.row_height - 8,
            )
            rect.setBrush(QColor(color).darker(130))
            rect.setPen(QColor(colors.BACKGROUND))
            self.scene.addItem(rect)

            # Texto do preço
            price_txt = QGraphicsTextItem(f"{bucket.price:.2f}")
            price_txt.setFont(font)
            price_txt.setDefaultTextColor(QColor(colors.MUTED))
            price_txt.setPos(0, y + 2)
            self.scene.addItem(price_txt)

            # Texto do volume
            vol_txt = QGraphicsTextItem(f"{bucket.volume:.2f}")
            vol_txt.setFont(font)
            vol_txt.setDefaultTextColor(QColor(colors.TEXT))
            vol_txt.setPos(x_origin + bar_width + 6, y + 2)
            self.scene.addItem(vol_txt)

        # Define tamanho total da cena
        self.setSceneRect(
            0,
            0,
            x_origin + width_max + 80,
            len(buckets_sorted) * self.row_height,
        )


    def update_profile(self, buckets, poc, vah, val):
        self.populate(buckets, poc, vah, val)


# ==========================================================
# PANEL — LIGAÇÃO AO ENGINE + REFRESH
# ==========================================================

class VolumeProfilePanel(QWidget):
    """
    Painel completo:
    - recebe dados do CoreDataEngine
    - agrega volume
    - atualiza a view
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("VolumeProfilePanel")
        self._logger = logging.getLogger(__name__)

        self._agg = VolumeProfileAggregator()
        self._pending = False

        # Timer de refresh (200ms)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(200)
        self._refresh_timer.timeout.connect(self._refresh_if_needed)


        # --------------------------------------------------
        # LAYOUT
        # --------------------------------------------------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        lbl = QLabel("Volume Profile")
        lbl.setFont(typography.inter(11, QFont.DemiBold))
        header.addWidget(lbl)
        header.addStretch()
        header.addWidget(self._legend("POC (Point of Control)", colors.HIGHLIGHT))
        header.addWidget(self._legend("Value Area (70%)", colors.ACCENT_BLUE))
        layout.addLayout(header)

        self.view = VolumeProfileView()
        layout.addWidget(self.view)

        # Ligar ao engine (com retry)
        QTimer.singleShot(0, self._wire_engine)

        self._refresh_timer.start()


    # ------------------------------------------------------
    # LEGENDA
    # ------------------------------------------------------
    def _legend(self, text: str, color_hex: str) -> QWidget:
        bubble = QFrame()
        bubble.setFixedSize(10, 10)
        bubble.setStyleSheet(f"background:{color_hex}; border-radius:5px;")

        lbl = QLabel(text)
        lbl.setFont(typography.inter(10))
        lbl.setStyleSheet(f"color:{colors.MUTED};")

        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.addWidget(bubble)
        h.addWidget(lbl)
        return container


    # ------------------------------------------------------
    # LIGAÇÃO AO CORE DATA ENGINE
    # ------------------------------------------------------
    def _wire_engine(self, attempts: int = 0):
        window = self.window()
        engine = getattr(window, "data_engine", None) if window else None

        if engine:
            try:
                # Garante que os sinais existem
                if not hasattr(engine, "trade") or not hasattr(engine, "candle_history"):
                    self._logger.warning("CoreDataEngine missing required signals; retrying...")
                    if attempts < 6:
                        QTimer.singleShot(150, lambda: self._wire_engine(attempts + 1))
                    return

                engine.trade.connect(self._on_trade)
                engine.candle_history.connect(self._on_candle_history)
                engine.candle_update.connect(self._on_candle_update)
                engine.timeframe_changed.connect(self._on_timeframe_changed)
                engine.symbol_changed.connect(self._on_symbol_changed)

                self._logger.info("VolumeProfilePanel wired to CoreDataEngine successfully")

            except Exception as e:
                self._logger.error("Failed to wire VolumeProfilePanel: %s", e)
                if attempts < 6:
                    QTimer.singleShot(150, lambda: self._wire_engine(attempts + 1))

        elif attempts < 6:
            QTimer.singleShot(150, lambda: self._wire_engine(attempts + 1))


    # ------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------
    def _on_trade(self, evt: TradeEvent):
        self._agg.add_trade(evt.trade)
        self._pending = True

    def _on_candle_history(self, evt: CandleHistory):
        self._agg.add_candles(evt.candles)
        self._pending = True

    def _on_candle_update(self, evt: CandleUpdate):
        self._agg.add_candle_update(evt.candle, evt.closed)
        self._pending = True

    def _on_timeframe_changed(self, evt: TimeframeChanged):
        self._agg.set_timeframe(evt.timeframe)
        self._pending = True

    def _on_symbol_changed(self, evt: SymbolChanged):
        self._agg.set_symbol(evt.symbol)
        self._pending = True


    # ------------------------------------------------------
    # REFRESH CONTROLADO
    # ------------------------------------------------------
    def _refresh_if_needed(self):
        if not self._pending:
            return

        self._pending = False
        buckets, poc, vah, val = self._agg.profile()
        self.view.update_profile(buckets, poc, vah, val)


    # ------------------------------------------------------
    # HOOK LEGACY (NÃO USADO)
    # ------------------------------------------------------
    def update_data(self, rows):
        pass
