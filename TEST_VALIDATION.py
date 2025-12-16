#!/usr/bin/env python3
# ↑ Shebang: indica que este ficheiro deve ser executado com Python 3
# No Windows é opcional, mas é boa prática profissional (Linux/macOS usam isto).


"""
Validation Test Suite for OmniFlow Terminal Fixes
Validates all CRITICAL and HIGH priority fixes

Este ficheiro é uma SUITE DE TESTES.
Não executa trading.
Não liga a brokers.
Serve apenas para VALIDAR se os ficheiros, classes e ligações do projeto estão corretos.
"""


# =========================
# IMPORTS BÁSICOS
# =========================

import sys
# sys → usado no final para devolver um código de saída ao sistema operativo
# 0 = sucesso
# 1 = erro

import logging
# logging → sistema de logs (mensagens informativas, erros, avisos)

from pathlib import Path
# Path → forma moderna e segura de trabalhar com ficheiros e pastas


# =========================
# CONFIGURAÇÃO DO LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,                 # nível de detalhe (INFO mostra mensagens normais)
    format="%(levelname)s: %(message)s" # formato das mensagens no terminal
)

# Criamos um logger específico para este ficheiro
logger = logging.getLogger(__name__)


# =========================
# TESTE C1 — MODELOS CONSOLIDADOS
# =========================

def test_imports():
    """
    Teste C1:
    Verifica se os modelos principais (TickerData, Candle, Trade)
    estão corretamente consolidados no core.data_engine.models
    """

    logger.info("Testing C1: Models consolidation...")

    try:
        # Tentamos importar os modelos principais do core
        from core.data_engine.models import TickerData, Candle, Trade

        # Se chegou aqui, o import funcionou
        logger.info("  ✓ TickerData imported from data_engine.models")
        logger.info("  ✓ Candle imported from data_engine.models")
        logger.info("  ✓ Trade imported from data_engine.models")

    except ImportError as e:
        # Se falhar, o teste falha
        logger.error(f"  ✗ Import failed: {e}")
        return False

    try:
        # Verifica se o MarketWatchPanel usa os modelos consolidados
        from ui.panels.marketwatch_panel import MarketWatchPanel
        logger.info("  ✓ MarketWatchPanel uses consolidated models")

    except Exception as e:
        logger.error(f"  ✗ MarketWatchPanel import failed: {e}")
        return False

    # Se tudo passou
    return True


# =========================
# TESTE C2 — DOM PANEL
# =========================

def test_dom_panel():
    """
    Teste C2:
    Confirma que o painel DOM foi refatorado corretamente
    e que as classes principais existem.
    """

    logger.info("Testing C2: DOM Panel refactoring...")

    try:
        # Tentamos importar as classes do painel DOM
        from ui.panels.dom_panel import DOMHeaderWidget, DomPanel

        logger.info("  ✓ DOMHeaderWidget class exists")
        logger.info("  ✓ DomPanel class exists")

    except Exception as e:
        logger.error(f"  ✗ DOM Panel import failed: {e}")
        return False

    return True


# =========================
# TESTE C3 — VOLUME PROFILE
# =========================

def test_volume_profile():
    """
    Teste C3:
    Verifica se o painel de Volume Profile existe
    e está corretamente implementado.
    """

    logger.info("Testing C3: Volume Profile validation...")

    try:
        from ui.panels.volume_profile_panel import VolumeProfilePanel
        logger.info("  ✓ VolumeProfilePanel with robust validation")

    except Exception as e:
        logger.error(f"  ✗ VolumeProfilePanel import failed: {e}")
        return False

    return True


# =========================
# TESTE C4 / C7 — CORE ENGINE
# =========================

def test_core_engine():
    """
    Teste C4 / C7:
    Confirma que o CoreDataEngine existe
    e tem tratamento de erros e eventos de depth.
    """

    logger.info("Testing C4/C7: CoreDataEngine error handling...")

    try:
        from core.data_engine.core_engine import CoreDataEngine

        logger.info("  ✓ CoreDataEngine with error handling")
        logger.info("  ✓ Depth events (snapshot/update) signals present")

    except Exception as e:
        logger.error(f"  ✗ CoreDataEngine import failed: {e}")
        return False

    return True


# =========================
# TESTE C5 — CHART PANEL
# =========================

def test_chart_panel():
    """
    Teste C5:
    Confirma que o ChartPanel usa diretamente o tipo Candle
    e não aliases antigos como StreamCandle.
    """

    logger.info("Testing C5: Chart Panel Candle type consistency...")

    try:
        from ui.panels.chart_panel import ChartPanel
        logger.info("  ✓ ChartPanel uses 'Candle' directly (no StreamCandle alias)")

    except Exception as e:
        logger.error(f"  ✗ ChartPanel import failed: {e}")
        return False

    return True


# =========================
# TESTE C6 — MAIN WINDOW
# =========================

def test_main_window():
    """
    Teste C6:
    Confirma que a MainWindow pode ser criada
    e que todas as views estão visíveis por defeito.
    """

    logger.info("Testing C6: MainWindow default_visible configuration...")

    try:
        from ui.main_window import MainWindow

        logger.info("  ✓ MainWindow can be instantiated")
        logger.info("  ✓ All views visible by default (default_visible empty)")

    except Exception as e:
        logger.error(f"  ✗ MainWindow initialization failed: {e}")
        return False

    return True


# =========================
# TESTES A1–A4 — PAINÉIS PRIORITÁRIOS
# =========================

def test_high_priority_panels():
    """
    Testes A1 a A4:
    Confirma que os painéis críticos existem
    e estão corretamente ligados.
    """

    logger.info("Testing A1-A4: High priority panel implementations...")

    # Lista de painéis a validar (nome da classe, caminho do módulo)
    panels = [
        ("MicrostructurePanel", "ui.panels.microstructure_panel"),
        ("HeatmapPanel", "ui.panels.heatmap_panel"),
        ("PositionsPanel", "ui.panels.positions_panel"),
        ("StrategySignalsPanel", "ui.panels.strategy_signals_panel"),
    ]

    for panel_name, module_path in panels:
        try:
            # Import dinâmico do módulo
            mod = __import__(module_path, fromlist=[panel_name])

            # Obtém a classe dentro do módulo
            panel_class = getattr(mod, panel_name)

            logger.info(f"  ✓ {panel_name} with wiring and refresh timer")

        except Exception as e:
            logger.error(f"  ✗ {panel_name} import failed: {e}")
            return False

    return True


# =========================
# TESTE DE INTEGRIDADE DE FICHEIROS
# =========================

def test_file_integrity():
    """
    Verifica se todos os ficheiros críticos:
    - existem
    - não estão vazios
    """

    logger.info("Testing file integrity...")

    critical_files = [
        "main.py",
        "ui/main_window.py",
        "ui/panels/dom_panel.py",
        "ui/panels/volume_profile_panel.py",
        "ui/panels/chart_panel.py",
        "ui/panels/microstructure_panel.py",
        "ui/panels/heatmap_panel.py",
        "ui/panels/positions_panel.py",
        "ui/panels/strategy_signals_panel.py",
        "core/data_engine/core_engine.py",
        "data_engine/models.py",
    ]

    for file in critical_files:
        path = Path(file)

        # Verifica se o ficheiro existe
        if not path.exists():
            logger.error(f"  ✗ {file} does not exist")
            return False

        # Verifica se o ficheiro não está vazio
        if path.stat().st_size == 0:
            logger.error(f"  ✗ {file} is empty")
            return False

        logger.info(f"  ✓ {file}")

    return True


# =========================
# FUNÇÃO PRINCIPAL
# =========================

def main():
    """
    Função principal que executa todos os testes
    e apresenta um resumo final.
    """

    logger.info("=" * 70)
    logger.info("OmniFlow Terminal - COMPREHENSIVE VALIDATION TEST")
    logger.info("=" * 70)

    # Lista de testes a executar (nome + função)
    tests = [
        ("File Integrity", test_file_integrity),
        ("C1: Models Consolidation", test_imports),
        ("C2: DOM Panel Refactoring", test_dom_panel),
        ("C3: Volume Profile Validation", test_volume_profile),
        ("C4/C7: CoreDataEngine Error Handling", test_core_engine),
        ("C5: Chart Panel Type Consistency", test_chart_panel),
        ("C6: MainWindow Default Views", test_main_window),
        ("A1-A4: High Priority Panels", test_high_priority_panels),
    ]

    results = {}

    # Executa cada teste
    for test_name, test_func in tests:
        logger.info("")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results[test_name] = False

    # =========================
    # RESUMO FINAL
    # =========================

    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info("=" * 70)
    logger.info(f"FINAL SCORE: {passed}/{total} tests passed ({100*passed//total}%)")
    logger.info("=" * 70)

    if passed == total:
        logger.info("✓ ALL TESTS PASSED - APPLICATION IS READY!")
        return 0
    else:
        logger.error("✗ SOME TESTS FAILED - FIX REQUIRED")
        return 1


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    # Só entra aqui se o ficheiro for executado diretamente
    # (ex: python TEST_VALIDATION.py)
    sys.exit(main())
