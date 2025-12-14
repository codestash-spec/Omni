from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QWidget


def create_dock(window, widget: QWidget, title: str, object_name: str) -> QDockWidget:
    dock = QDockWidget(title, window)
    dock.setObjectName(object_name)
    dock.setWidget(widget)
    dock.setAllowedAreas(Qt.AllDockWidgetAreas)
    dock.setFeatures(
        QDockWidget.DockWidgetMovable |
        QDockWidget.DockWidgetClosable |
        QDockWidget.DockWidgetFloatable
    )
    return dock


def apply_default_layout(main, docks):
    main.setUpdatesEnabled(False)
    
    # 🔥 ADICIONAR ESTAS LINHAS ANTES DE TUDO
    for dock in docks.values():
        dock.setFloating(False)  # Garantir que não está flutuando
        dock.hide()  # Esconder antes de remover
        try:
            main.removeDockWidget(dock)
        except:
            pass
    
    # ===============================
    # 1️⃣ CRIAR 3 ÂNCORAS INDEPENDENTES
    # ===============================
    # Coluna Esquerda
    main.addDockWidget(Qt.LeftDockWidgetArea, docks["marketwatch"])
    
    # Coluna Central - usar Bottom como âncora temporária
    main.addDockWidget(Qt.BottomDockWidgetArea, docks["price_chart"])
    
    # Coluna Direita
    main.addDockWidget(Qt.RightDockWidgetArea, docks["time_sales"])

    # ===============================
    # 2️⃣ REPOSICIONAR COLUNA CENTRAL
    # ===============================
    main.splitDockWidget(docks["marketwatch"], docks["price_chart"], Qt.Horizontal)
    main.splitDockWidget(docks["price_chart"], docks["time_sales"], Qt.Horizontal)

    # ===============================
    # 3️⃣ EMPILHAR VERTICALMENTE - COLUNA ESQUERDA
    # ===============================
    main.tabifyDockWidget(docks["marketwatch"], docks["positions_panel"])
    main.tabifyDockWidget(docks["positions_panel"], docks["news_panel"])

    # ===============================
    # 4️⃣ EMPILHAR VERTICALMENTE - COLUNA CENTRAL
    # ===============================
    main.tabifyDockWidget(docks["price_chart"], docks["microstructure_panel"])
    main.tabifyDockWidget(docks["microstructure_panel"], docks["heatmap_panel"])

    # ===============================
    # 5️⃣ EMPILHAR VERTICALMENTE - COLUNA DIREITA
    # ===============================
    main.tabifyDockWidget(docks["time_sales"], docks["footprint"])
    main.tabifyDockWidget(docks["footprint"], docks["dom_ladder"])
    main.tabifyDockWidget(docks["dom_ladder"], docks["volume_profile"])

    # ===============================
    # 6️⃣ MOSTRAR OS DOCKS PRINCIPAIS
    # ===============================
    for dock in docks.values():
        dock.show()

    docks["marketwatch"].raise_()
    docks["price_chart"].raise_()
    docks["time_sales"].raise_()

    main.setUpdatesEnabled(True)