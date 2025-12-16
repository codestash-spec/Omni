# ==========================================================
# IMPORTS
# ==========================================================

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Qt Core / GUI
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
    QLabel,
    QHBoxLayout,
)

# Core events (book + trades)
from core.data_engine.events import (
    DepthSnapshotEvent,
    DepthUpdateEvent,
    TradeEvent,
)

# UI theme
from ui.theme import colors, typography


# ==========================================================
# DATA STRUCTURE — DEPTH LEVEL
# ==========================================================

@dataclass
class DepthLevel:
    """
    Representa um nível de book:
    - price: preço
    - size: quantidade
    """
    price: float
    size: float


# ==========================================================
# DEPTH MODEL — ORDER BOOK STATE
# ==========================================================

class DepthModel:
    """
    Modelo lógico do Order Book (DOM).

    Mantém:
    - bids (compras)
    - asks (vendas)
    - último preço negociado
    """

    def __init__(self):
        self.bids: Dict[float, float] = {}
        self.asks: Dict[float, float] = {}
        self.last_price: Optional[float] = None


    # --------------------------
    # SNAPSHOT COMPLETO
    # --------------------------

    def apply_snapshot(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
    ):
        """
        Substitui completamente o book.
        Usado no snapshot inicial.
        """
        self.bids = {p: s for p, s in bids if s > 0}
        self.asks = {p: s for p, s in asks if s > 0}


    # --------------------------
    # UPDATE INCREMENTAL
    # --------------------------

    def apply_update(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
    ):
        """
        Aplica updates incrementais:
        - size = 0 → remove nível
        - size > 0 → atualiza nível
        """
        for p, s in bids:
            if s == 0:
                self.bids.pop(p, None)
            else:
                self.bids[p] = s

        for p, s in asks:
            if s == 0:
                self.asks.pop(p, None)
            else:
                self.asks[p] = s


    # --------------------------
    # QUERY TOP LEVELS
    # --------------------------

    def top(self, depth: int = 15):
        """
        Retorna os N melhores bids e asks.
        """
        bids_sorted = sorted(
            self.bids.items(),
            key=lambda x: x[0],
            reverse=True,
        )[:depth]

        asks_sorted = sorted(
            self.asks.items(),
            key=lambda x: x[0],
        )[:depth]

        return bids_sorted, asks_sorted

    def best_bid(self):
        return max(self.bids.keys()) if self.bids else None

    def best_ask(self):
        return min(self.asks.keys()) if self.asks else None


# ==========================================================
# LADDER VIEW — RENDERIZAÇÃO DO DOM
# ==========================================================

class LadderView(QGraphicsView):
    """
    Renderização gráfica do DOM Ladder.
    """

    def __init__(self, parent=None, levels=15):
        super().__init__(parent)

        # Qualidade gráfica
        self.setRenderHint(QPainter.Antialiasing, True)

        # Scroll vertical apenas
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # Configuração visual
        self.row_height = 24
        self.levels = levels
        self.headers = ["Size", "Bid", "Price", "Ask", "Size"]

        self.font = typography.mono(10)
        self.price_font = typography.inter(10, QFont.DemiBold)

        # Cache das rows gráficas
        self.rows: List[Dict[str, QGraphicsRectItem | QGraphicsTextItem]] = []

        # Para recentrar no último preço
        self._last_center_price: Optional[float] = None

        self._init_rows()


    # --------------------------
    # CONSTRUÇÃO ESTÁTICA
    # --------------------------

    def _init_rows(self):
        """
        Cria todas as rows e headers uma vez.
        """
        self.scene.clear()

        cols = [80, 70, 90, 70, 80]
        self.col_widths = cols

        self.col_x = [0]
        for w in cols[:-1]:
            self.col_x.append(self.col_x[-1] + w)

        # Headers
        y_offset = 22
        for header, x in zip(self.headers, self.col_x):
            txt = self.scene.addText(
                header,
                typography.inter(10, QFont.DemiBold),
            )
            txt.setDefaultTextColor(QColor(colors.MUTED))
            txt.setPos(x + 4, 2)

        total_rows = self.levels * 2 + 1  # bids + mid + asks

        for idx in range(total_rows):
            y = y_offset + idx * self.row_height

            # Background bars
            bid_rect = QGraphicsRectItem(
                self.col_x[0],
                y + 2,
                self.col_widths[0] + self.col_widths[1],
                self.row_height - 4,
            )
            bid_rect.setPen(QColor(colors.BACKGROUND))

            ask_rect = QGraphicsRectItem(
                self.col_x[2],
                y + 2,
                self.col_widths[2] + self.col_widths[3] + self.col_widths[4],
                self.row_height - 4,
            )
            ask_rect.setPen(QColor(colors.BACKGROUND))

            self.scene.addItem(bid_rect)
            self.scene.addItem(ask_rect)

            # Text items
            bid_size = self.scene.addText("", self.font)
            bid_size.setDefaultTextColor(QColor(colors.ACCENT_GREEN))

            bid_price = self.scene.addText("", self.font)
            bid_price.setDefaultTextColor(QColor(colors.ACCENT_GREEN))

            mid_price = self.scene.addText("", self.price_font)
            mid_price.setDefaultTextColor(QColor(colors.TEXT))

            ask_price = self.scene.addText("", self.font)
            ask_price.setDefaultTextColor(QColor(colors.ACCENT_RED))

            ask_size = self.scene.addText("", self.font)
            ask_size.setDefaultTextColor(QColor(colors.ACCENT_RED))

            for t in (
                bid_size,
                bid_price,
                mid_price,
                ask_price,
                ask_size,
            ):
                self.scene.addItem(t)

            self.rows.append(
                {
                    "bid_rect": bid_rect,
                    "ask_rect": ask_rect,
                    "bid_size": bid_size,
                    "bid_price": bid_price,
                    "mid_price": mid_price,
                    "ask_price": ask_price,
                    "ask_size": ask_size,
                }
            )

        self.setSceneRect(
            0,
            0,
            sum(self.col_widths),
            y_offset + total_rows * self.row_height,
        )


    # --------------------------
    # RENDERIZAÇÃO DINÂMICA
    # --------------------------

    def render_levels(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        last_price: Optional[float],
    ):
        """
        Atualiza visualmente o DOM.
        """
        bids = [(p, s) for p, s in bids if s > 0]
        asks = [(p, s) for p, s in asks if s > 0]

        max_size = max([s for _, s in bids + asks], default=1.0)

        half = self.levels
        center_idx = half

        for idx, row in enumerate(self.rows):
            y = 22 + idx * self.row_height

            # Reset
            for key in (
                "bid_size",
                "bid_price",
                "mid_price",
                "ask_price",
                "ask_size",
            ):
                item: QGraphicsTextItem = row[key]  # type: ignore
                item.setPlainText("")

            row["bid_rect"].setBrush(QColor(colors.BACKGROUND))
            row["ask_rect"].setBrush(QColor(colors.BACKGROUND))

            # --------------------------
            # BIDS
            # --------------------------
            if idx < center_idx:
                bid_idx = idx
                if bid_idx < len(bids):
                    price, size = bids[bid_idx]
                    bar_w = (
                        (self.col_widths[0] + self.col_widths[1])
                        * min(1.0, size / max_size)
                    )

                    row["bid_rect"].setBrush(
                        QColor(colors.ACCENT_GREEN).lighter(120)
                    )
                    row["bid_rect"].setRect(
                        self.col_x[1] + (self.col_widths[1] - bar_w),
                        y + 2,
                        bar_w,
                        self.row_height - 4,
                    )

                    row["bid_size"].setPlainText(f"{size:,.0f}")
                    row["bid_size"].setPos(self.col_x[0] + 6, y + 4)

                    row["bid_price"].setPlainText(f"{price:.2f}")
                    row["bid_price"].setPos(self.col_x[1] + 6, y + 4)

            # --------------------------
            # MID PRICE
            # --------------------------
            elif idx == center_idx:
                mid = (
                    last_price
                    if last_price is not None
                    else ((bids[0][0] + asks[0][0]) / 2 if bids and asks else 0.0)
                )

                row["mid_price"].setPlainText(f"{mid:.2f}")
                row["mid_price"].setPos(self.col_x[2] - 6, y + 4)
                row["mid_price"].setDefaultTextColor(
                    QColor(colors.HIGHLIGHT)
                )

            # --------------------------
            # ASKS
            # --------------------------
            else:
                ask_idx = idx - center_idx - 1
                if ask_idx < len(asks):
                    price, size = asks[ask_idx]
                    bar_w = (
                        (self.col_widths[2] + self.col_widths[3])
                        * min(1.0, size / max_size)
                    )

                    row["ask_rect"].setBrush(
                        QColor(colors.ACCENT_RED).lighter(120)
                    )
                    row["ask_rect"].setRect(
                        self.col_x[2],
                        y + 2,
                        bar_w,
                        self.row_height - 4,
                    )

                    row["ask_price"].setPlainText(f"{price:.2f}")
                    row["ask_price"].setPos(self.col_x[2] + 6, y + 4)

                    row["ask_size"].setPlainText(f"{size:,.0f}")
                    row["ask_size"].setPos(self.col_x[4] - 50, y + 4)

        # Auto-centering no último preço
        if last_price:
            if self._last_center_price != last_price:
                center_y = 22 + center_idx * self.row_height
                self.centerOn(
                    (self.col_x[2] + self.col_widths[2] / 2),
                    center_y,
                )
                self._last_center_price = last_price


# ==========================================================
# DOM PANEL — CONTROLLER
# ==========================================================

class DomPanel(QWidget):
    """
    Painel DOM Ladder completo.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("DomPanel")
        self._logger = logging.getLogger(__name__)

        self._model = DepthModel()

        self._pending_snapshot: Optional[DepthSnapshotEvent] = None
        self._pending_update: Optional[DepthUpdateEvent] = None
        self._last_trade_price: Optional[float] = None

        # Timer de flush controlado
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(80)  # ~12 Hz
        self._flush_timer.timeout.connect(self._flush_depth)

        self._wire_attempts = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(DOMHeaderWidget("DOM Ladder"))

        self.ladder = LadderView(levels=15)
        layout.addWidget(self.ladder)

        QTimer.singleShot(0, self._wire_engine)
        self._flush_timer.start()


    # --------------------------
    # ENGINE WIRING
    # --------------------------

    def _wire_engine(self):
        if self._wire_attempts > 6:
            return

        self._wire_attempts += 1

        window = self.window()
        engine = getattr(window, "data_engine", None) if window else None

        if engine:
            engine.depth_snapshot.connect(self.on_depth_snapshot)
            engine.depth_update.connect(self.on_depth_update)
            if hasattr(engine, "trade"):
                engine.trade.connect(self.on_trade_event)
        else:
            QTimer.singleShot(100, self._wire_engine)


    # --------------------------
    # EVENT HANDLERS
    # --------------------------

    def on_trade_event(self, evt: TradeEvent):
        self._last_trade_price = evt.trade.price

    def on_depth_snapshot(self, evt: DepthSnapshotEvent):
        self._pending_snapshot = evt

    def on_depth_update(self, evt: DepthUpdateEvent):
        self._pending_update = evt


    # --------------------------
    # FLUSH CONTROLADO
    # --------------------------

    def _flush_depth(self):
        if self._pending_snapshot:
            snap = self._pending_snapshot
            self._model.apply_snapshot(snap.bids, snap.asks)
            self._pending_snapshot = None

        if self._pending_update:
            upd = self._pending_update
            self._model.apply_update(upd.bids, upd.asks)
            self._pending_update = None

        bids, asks = self._model.top()
        last_price = self._last_trade_price

        if not last_price and bids and asks:
            last_price = (bids[0][0] + asks[0][0]) / 2

        self.ladder.render_levels(bids, asks, last_price)


    # --------------------------
    # LEGACY
    # --------------------------

    def update_data(self, rows):
        """
        Hook legado (debug / fallback).
        """
        if isinstance(rows, list):
            self._model.apply_snapshot(
                [(r["price"], r.get("bid", 0)) for r in rows],
                [],
            )
            self._pending_update = None
            self._pending_snapshot = None


# ==========================================================
# HEADER WIDGET
# ==========================================================

class DOMHeaderWidget(QWidget):
    """
    Header simples do painel DOM.
    """

    def __init__(self, text: str, parent=None):
        super().__init__(parent)

        lbl = QLabel(text)
        lbl.setFont(typography.inter(11, QFont.DemiBold))
        lbl.setStyleSheet(f"color:{colors.TEXT};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 0, 0)
        layout.addWidget(lbl)
