# Importa constantes e enums do Qt (Left, Right, Bottom, Horizontal, etc.)
from PySide6.QtCore import Qt

# Importa widgets base do Qt
from PySide6.QtWidgets import QDockWidget, QWidget


# ==========================================================
# FUNÇÃO: create_dock
# ==========================================================
# Cria um Dock (painel acoplável) configurado de forma padrão
# para ser usado na MainWindow.
#
# window      → janela principal (MainWindow)
# widget      → o painel real (MarketWatch, DOM, Chart, etc.)
# title       → título visível no topo do dock
# object_name → identificador único (usado para estilos e debug)
#
# Retorna: QDockWidget pronto a usar
# ==========================================================
def create_dock(window, widget: QWidget, title: str, object_name: str) -> QDockWidget:

    # Cria o dock e associa-o à janela principal
    dock = QDockWidget(title, window)

    # Define um nome interno (importante para estilos, estado e debug)
    dock.setObjectName(object_name)

    # Coloca o widget real (painel) dentro do dock
    dock.setWidget(widget)

    # Permite que este dock seja colocado em qualquer lado da janela
    dock.setAllowedAreas(Qt.AllDockWidgetAreas)

    # Define o que o utilizador pode fazer com o dock
    dock.setFeatures(
        QDockWidget.DockWidgetMovable |
        QDockWidget.DockWidgetClosable |
        QDockWidget.DockWidgetFloatable
    )

    return dock


# ==========================================================
# FUNÇÃO: apply_default_layout
# ==========================================================
# Aplica o layout INICIAL da aplicação.
#
# Responsável por:
# - limpar layouts antigos
# - criar 3 colunas reais (esquerda, centro, direita)
# - empilhar docks corretamente
# - garantir que o Qt NÃO colapsa para 2 colunas
#
# main  → MainWindow
# docks → dicionário com todos os docks
# ==========================================================
def apply_default_layout(main, docks):

    # Evita glitches visuais durante rearranjo
    main.setUpdatesEnabled(False)

    # ======================================================
    # LIMPEZA TOTAL DO ESTADO ANTERIOR
    # ======================================================
    for dock in docks.values():
        dock.setFloating(False)
        dock.hide()
        try:
            main.removeDockWidget(dock)
        except Exception:
            pass

    # ======================================================
    # 1️⃣ CRIAR ÂNCORAS DAS 3 COLUNAS
    # ======================================================

    # 🟦 ESQUERDA
    main.addDockWidget(Qt.LeftDockWidgetArea, docks["marketwatch"])

    # 🟩 CENTRO (âncora temporária)
    main.addDockWidget(Qt.BottomDockWidgetArea, docks["price_chart"])

    # 🟥 DIREITA
    main.addDockWidget(Qt.RightDockWidgetArea, docks["time_sales"])

    # ======================================================
    # 2️⃣ FORÇAR 3 COLUNAS HORIZONTAIS
    # ======================================================

    main.splitDockWidget(
        docks["marketwatch"],
        docks["price_chart"],
        Qt.Horizontal
    )

    main.splitDockWidget(
        docks["price_chart"],
        docks["time_sales"],
        Qt.Horizontal
    )

    # ======================================================
    # 3️⃣ EMPILHAR COLUNA ESQUERDA
    # ======================================================

    main.tabifyDockWidget(docks["marketwatch"], docks["positions_panel"])
    main.tabifyDockWidget(docks["marketwatch"], docks["strategy_panel"])
    main.tabifyDockWidget(docks["strategy_panel"], docks["news_panel"])

    # ======================================================
    # 4️⃣ EMPILHAR COLUNA CENTRAL
    # ======================================================

    main.tabifyDockWidget(docks["price_chart"], docks["microstructure_panel"])
    main.tabifyDockWidget(docks["microstructure_panel"], docks["heatmap_panel"])

    # ======================================================
    # 5️⃣ EMPILHAR COLUNA DIREITA
    # ======================================================

    main.tabifyDockWidget(docks["time_sales"], docks["footprint"])
    main.tabifyDockWidget(docks["footprint"], docks["dom_ladder"])
    main.tabifyDockWidget(docks["dom_ladder"], docks["volume_profile"])

    # ======================================================
    # 6️⃣ MOSTRAR TODOS OS DOCKS
    # ======================================================

    for dock in docks.values():
        dock.show()

    # ======================================================
    # 7️⃣ DEFINIR DOCK ATIVO EM CADA COLUNA
    # ======================================================

    docks["marketwatch"].raise_()
    docks["price_chart"].raise_()
    docks["time_sales"].raise_()

    # ======================================================
    # 8️⃣ REATIVAR UPDATES
    # ======================================================

    main.setUpdatesEnabled(True)
