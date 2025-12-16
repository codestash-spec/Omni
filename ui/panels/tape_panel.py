# ==========================================================
# IMPORTS BASE
# ==========================================================

# deque → buffer eficiente FIFO
from collections import deque

# datetime → formatação do timestamp das trades
from datetime import datetime

import logging
import time


# ==========================================================
# IMPORTS QT
# ==========================================================

from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


# ==========================================================
# TEMA + MODELOS
# ==========================================================

from ui.theme import colors, typography
from core.data_engine.models import Trade


# ==========================================================
# TAPE PANEL
# ==========================================================

class TapePanel(QWidget):
    """
    Painel de Time & Sales / Tape Reading.

    Funcionalidades principais:
    - Mostra trades em tempo real
    - Modos de tamanho:
        • BASE  → quantidade base
        • QUOTE → valor em USD (default)
        • COMPACT → K / M
    - Flags heurísticas:
        • Block
        • Sweep
        • Iceberg
        • Absorption
    - Filtros:
        • Aggressive Only
        • Block trades only
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("TapePanel")
        self._logger = logging.getLogger(__name__)


        # ==================================================
        # BUFFERS INTERNOS
        # ==================================================

        # Trades já renderizadas (linhas da tabela)
        self._trades: deque[dict] = deque(maxlen=120)

        # Buckets vivos para acumulação temporal
        self._live_buckets: dict[str, dict] = {}

        # Trades recebidas mas ainda não processadas
        self._pending: deque[Trade] = deque(maxlen=500)

        # Trades recentes usados para derivar flags
        self._recent_for_flags: deque[Trade] = deque(maxlen=400)


        # ==================================================
        # SETTINGS (PERSISTENTES)
        # ==================================================

        self._settings = QSettings("OmniFlow", "TapePanel")
        self._load_settings()


        # ==================================================
        # TIMER DE FLUSH (UI SAFE)
        # ==================================================

        # Atualiza a UI ~20 vezes por segundo
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(50)
        self._flush_timer.timeout.connect(self._flush_pending)
        self._flush_timer.start()


        # ==================================================
        # LAYOUT
        # ==================================================

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        lbl = QLabel("Tape Reading")
        lbl.setFont(typography.inter(11, QFont.DemiBold))
        header.addWidget(lbl)
        header.addStretch()

        # Checkboxes ocultos (controlados via SettingsDialog)
        self.aggr_only = QCheckBox("Aggressive Only")
        self.blocks_only = QCheckBox("Block Trades")
        self.aggr_only.setVisible(False)
        self.blocks_only.setVisible(False)

        layout.addLayout(header)


        # ==================================================
        # TABELA DE TRADES
        # ==================================================

        self.table = QTableWidget(12, 5)
        self.table.setHorizontalHeaderLabels(
            ["Time", "Price", "Size", "Side", "Flags"]
        )

        header_view = self.table.horizontalHeader()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        header_view.setMinimumSectionSize(60)

        # Larguras / comportamentos por coluna
        header_view.resizeSection(0, 110)                     # Time
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Price
        header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Size
        header_view.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Side
        header_view.setSectionResizeMode(4, QHeaderView.Stretch)           # Flags

        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        self.table.setMouseTracking(True)

        # Estilo hover / seleção
        self.table.setStyleSheet(
            """
            QTableWidget::item:selected { background-color: rgba(80,120,200,80); }
            QTableWidget::item:hover { background-color: rgba(255,255,255,25); }
            """
        )

        layout.addWidget(self.table)


    # ======================================================
    # SETTINGS
    # ======================================================

    def _load_settings(self):
        """
        Carrega settings persistentes (QSettings)
        """
        self._size_mode = str(self._settings.value("size_mode", "QUOTE") or "QUOTE")

        self._min_notional_filter = float(self._settings.value("min_notional_filter", 0.0))
        self._block_threshold = float(self._settings.value("block_threshold", 100_000.0))

        self._aggr_only_enabled = self._as_bool(self._settings.value("aggr_only", False))
        self._blocks_only_enabled = self._as_bool(self._settings.value("blocks_only", False))
        self._flags_enabled = self._as_bool(self._settings.value("flags_enabled", False))

        self._acc_interval_ms = int(self._settings.value("accumulation_interval_ms", 0))

        # Iceberg
        self._iceberg_window_ms = int(self._settings.value("iceberg_window_ms", 400))
        self._iceberg_count = int(self._settings.value("iceberg_count", 5))

        # Sweep
        self._sweep_window_ms = int(self._settings.value("sweep_window_ms", 300))
        self._sweep_price_levels = int(self._settings.value("sweep_price_levels", 4))
        self._sweep_min_notional = float(self._settings.value("sweep_min_notional", 5_000.0))
        self._sweep_min_price_diff = float(self._settings.value("sweep_min_price_diff", 1.0))

        # Absorption
        self._absorb_window_ms = int(self._settings.value("absorb_window_ms", 800))
        self._absorb_volume = float(self._settings.value("absorb_volume", 20_000.0))


    def reload_settings(self):
        """
        Chamado quando o SettingsDialog é aceite
        """
        self._load_settings()
        self.aggr_only.setChecked(self._aggr_only_enabled)
        self.blocks_only.setChecked(self._blocks_only_enabled)
        self.populate(list(self._trades))


    # ======================================================
    # INGESTÃO DE DADOS
    # ======================================================

    def on_trade(self, trade: Trade):
        """
        Recebe trades do CoreDataEngine.
        Apenas coloca na fila para não bloquear a UI.
        """
        self._pending.append(trade)


    # ======================================================
    # FLUSH (CORE → UI)
    # ======================================================

    def _flush_pending(self):
        """
        Processa trades pendentes em batches pequenos
        para manter a UI fluida.
        """
        if not self._pending:
            return

        max_batch = 100          # limite por frame
        time_budget = 0.01       # ~10ms
        start = time.perf_counter()

        new_rows: list[dict] = []
        finalized: list[dict] = []
        live_rows: list[dict] = []

        use_acc = self._acc_interval_ms > 0
        processed = 0

        while self._pending and processed < max_batch:
            trade = self._pending.popleft()
            processed += 1

            # Timestamp formatado
            ts = datetime.utcfromtimestamp(trade.ts / 1000)
            formatted = ts.strftime("%H:%M:%S.%f")[:-3]

            notional = trade.price * trade.qty

            # Derivar flags
            flags = self._derive_flags(trade, notional)

            # Guardar trade para heurísticas futuras
            self._recent_for_flags.append(trade)

            # Filtros
            if (self.blocks_only.isChecked() or self._blocks_only_enabled) and "Block" not in flags:
                continue

            if (self.aggr_only.isChecked() or self._aggr_only_enabled) and notional < self._min_notional_filter:
                continue

            # Sem acumulação → linha direta
            if not use_acc:
                new_rows.append(
                    self._make_row(
                        formatted,
                        trade.ts,
                        trade.price,
                        trade.qty,
                        notional,
                        trade.side,
                        flags,
                    )
                )

            # Com acumulação → buckets
            else:
                bucket_id = trade.ts // self._acc_interval_ms
                live = self._live_buckets.get(trade.side)

                if live and live["bucket"] != bucket_id:
                    self._finalize_bucket(live, finalized)
                    self._live_buckets.pop(trade.side, None)
                    live = None

                if not live:
                    live = {
                        "bucket": bucket_id,
                        "qty": 0.0,
                        "notional": 0.0,
                        "vw_sum": 0.0,
                        "ts": trade.ts,
                        "side": trade.side,
                        "flags": set(),
                    }

                live["qty"] += trade.qty
                live["notional"] += notional
                live["vw_sum"] += trade.price * trade.qty
                live["ts"] = max(live["ts"], trade.ts)
                live["flags"].update(flags)

                self._live_buckets[trade.side] = live

            if time.perf_counter() - start >= time_budget:
                break

        # ==================================================
        # ATUALIZAÇÃO DA TABELA
        # ==================================================

        if use_acc:
            for side, live in list(self._live_buckets.items()):
                live_rows.append(self._make_row_from_bucket(live, live=True))

            finalized.sort(key=lambda r: r["ts"], reverse=True)
            for row in finalized:
                self._trades.appendleft(row)

            display_rows = live_rows + list(self._trades)

        else:
            new_rows.sort(key=lambda r: r["ts"], reverse=True)
            for row in new_rows:
                self._trades.appendleft(row)

            display_rows = list(self._trades)

        self.populate(display_rows)


    # ======================================================
    # RENDERIZAÇÃO
    # ======================================================

    def populate(self, rows: list[dict]):
        """
        Renderiza as linhas na tabela
        """
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            # Criação de itens
            time_item = QTableWidgetItem(row["time"])
            price_item = QTableWidgetItem(f"{row['price']:.2f}")
            size_item = QTableWidgetItem(str(row["size"]))
            side_item = QTableWidgetItem(row["side"])
            flags_item = QTableWidgetItem(row.get("flags", ""))

            # Cor por lado
            side_color = (
                colors.ACCENT_GREEN if row["side"] == "Buy"
                else colors.ACCENT_RED if row["side"] == "Sell"
                else colors.MUTED
            )

            price_item.setForeground(QColor(side_color))
            side_item.setForeground(QColor(side_color))

            for item in [time_item, price_item, size_item, side_item, flags_item]:
                item.setFont(typography.mono(10))
                item.setTextAlignment(
                    Qt.AlignRight | Qt.AlignVCenter
                    if item in (price_item, size_item, flags_item)
                    else Qt.AlignCenter
                )

            # Size em bold
            f = size_item.font()
            f.setBold(True)
            size_item.setFont(f)

            # Inserir na tabela
            self.table.setItem(r, 0, time_item)
            self.table.setItem(r, 1, price_item)
            self.table.setItem(r, 2, size_item)
            self.table.setItem(r, 3, side_item)
            self.table.setItem(r, 4, flags_item)

        self.table.setUpdatesEnabled(True)


    # ======================================================
    # FLAGS HEURÍSTICAS
    # ======================================================

    def _derive_flags(self, trade: Trade, notional: float) -> list[str]:
        """
        Heurísticas simples (sem chamadas externas):
        - Block
        - Iceberg
        - Sweep
        - Absorption
        """
        if not self._flags_enabled:
            return []

        flags: list[str] = []

        # Block
        if notional >= self._block_threshold:
            flags.append("Block")

        now_ms = trade.ts

        # Iceberg
        recent = [t for t in self._recent_for_flags if now_ms - t.ts <= self._iceberg_window_ms]
        same_price = [t for t in recent if abs(t.price - trade.price) < 1e-6]
        if len(same_price) >= self._iceberg_count and notional < self._block_threshold * 0.05:
            flags.append("Iceberg")

        # Sweep
        recent_sweep = [t for t in self._recent_for_flags if now_ms - t.ts <= self._sweep_window_ms]
        prices = [t.price for t in recent_sweep]
        if prices:
            price_range = max(prices) - min(prices)
            unique_prices = {round(p, 2) for p in prices}
            sweep_notional = sum(t.price * t.qty for t in recent_sweep)
            if (
                len(unique_prices) >= self._sweep_price_levels
                and price_range >= self._sweep_min_price_diff
                and sweep_notional >= self._sweep_min_notional
            ):
                flags.append("Sweep")

        # Absorption
        absorb_recent = [
            t for t in self._recent_for_flags
            if now_ms - t.ts <= self._absorb_window_ms and abs(t.price - trade.price) < 1e-6
        ]
        if sum(t.price * t.qty for t in absorb_recent) >= self._absorb_volume:
            flags.append("Absorb")

        return flags


    # ======================================================
    # HELPERS
    # ======================================================

    def _format_size(self, base_qty: float, notional: float) -> str:
        """
        Formata o tamanho conforme o modo selecionado
        """
        if self._size_mode == "BASE":
            return f"{base_qty:.4f}"

        if self._size_mode == "COMPACT":
            if notional < 1_000:
                return f"{notional:.0f}"
            if notional < 1_000_000:
                return f"{notional/1_000:.1f}K"
            return f"{notional/1_000_000:.2f}M"

        # QUOTE (default)
        return f"${notional:,.2f}"


    def _as_bool(self, val) -> bool:
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        if isinstance(val, (int, float)):
            return val != 0
        return str(val).strip().lower() in ("1", "true", "yes", "on")
