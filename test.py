"""
==========================================================
TESTE DE PIPELINE DE DADOS — OMNIFLOW
==========================================================

Este script testa:
1) Se o CoreDataEngine arranca
2) Se o BinanceProvider recebe dados
3) Se os eventos (tickers, trades, candles) são emitidos
4) Se os dados têm conteúdo real

❗ NÃO usa UI
❗ NÃO cria janelas
❗ NÃO depende de MainWindow
"""

import sys
import time
import logging

from PySide6.QtCore import QCoreApplication, QTimer

# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger("TEST")


# ---------------------------------------------------------
# IMPORTS DO CORE
# ---------------------------------------------------------

from core.app_state import AppState
from core.data_engine.core_engine import CoreDataEngine


# ---------------------------------------------------------
# CALLBACKS DE TESTE
# ---------------------------------------------------------

def on_tickers(evt):
    logger.warning("✅ RECEBIDO TICKERS: %d símbolos", len(evt.tickers))

    # Mostra 5 exemplos reais
    for row in evt.tickers[:5]:
        logger.warning(
            "   %s | price=%s | vol=%s",
            getattr(row, "symbol", "?"),
            getattr(row, "last_price", "?"),
            getattr(row, "volume", "?"),
        )


def on_trade(evt):
    trade = evt.trade
    logger.warning(
        "💥 TRADE: %s %s @ %s qty=%s",
        trade.symbol,
        trade.side,
        trade.price,
        trade.qty,
    )


def on_candle_history(evt):
    logger.warning(
        "📊 CANDLES: %s %s -> %d candles",
        evt.symbol,
        evt.timeframe,
        len(evt.candles),
    )


def on_candle_update(evt):
    logger.warning(
        "🕯️ CANDLE UPDATE: %s %s close=%s",
        evt.symbol,
        evt.timeframe,
        evt.candle.close,
    )


# ---------------------------------------------------------
# MAIN TEST
# ---------------------------------------------------------

def main():
    logger.info("=" * 70)
    logger.info("INICIAR TESTE DE PIPELINE DE DADOS (HEADLESS)")
    logger.info("=" * 70)

    app = QCoreApplication(sys.argv)

    # Estado global
    app_state = AppState()

    # Engine
    engine = CoreDataEngine(
        parent=None,
        initial_symbol=app_state.current_symbol,
        initial_timeframe="1m",
    )

    # -----------------------------------------------------
    # LIGAR EVENTOS
    # -----------------------------------------------------

    engine.tickers.connect(on_tickers)
    engine.trade.connect(on_trade)
    engine.candle_history.connect(on_candle_history)
    engine.candle_update.connect(on_candle_update)

    # -----------------------------------------------------
    # START ENGINE
    # -----------------------------------------------------

    logger.info("🚀 A arrancar CoreDataEngine...")
    engine.start()

    # -----------------------------------------------------
    # TIMER DE SEGURANÇA (encerra após 15s)
    # -----------------------------------------------------

    def stop_test():
        logger.info("⛔ TESTE TERMINADO (timeout)")
        engine.stop()
        app.quit()

    QTimer.singleShot(15_000, stop_test)

    app.exec()


# ---------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------

if __name__ == "__main__":
    main()
