import json
import os
import sys
from pathlib import Path

# ==========================================================
# AJUSTE DE PATH PARA IMPORTS DO PROJETO
# ==========================================================
# Garante que a raiz do projeto está no sys.path
# permitindo executar este script de qualquer pasta
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ==========================================================
# QT IMPORTS (HEADLESS)
# ==========================================================
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

# ==========================================================
# MAIN WINDOW
# ==========================================================
from ui.main_window import MainWindow


# ==========================================================
# DOCKS ESPERADOS
# ==========================================================
# Lista canónica de todos os docks que DEVEM existir
# Serve como contrato visual da aplicação
EXPECTED_DOCKS = [
    "dock_marketwatch",
    "dock_positions",
    "dock_news",
    "dock_strategy_signals",
    "dock_time_sales",
    "dock_price_chart",
    "dock_dom_ladder",
    "dock_footprint",
    "dock_volume_profile",
    "dock_liquidity_heatmap",
    "dock_microstructure",
]


# ==========================================================
# COLETOR DE ESTADO DO LAYOUT
# ==========================================================
def collect_state(win: MainWindow):
    """
    Extrai o estado completo de todos os docks:
    - visibilidade
    - floating
    - área (left/right/top/bottom)
    - tabificação
    - geometria
    """
    state = {}
    for key, dock in win.docks.items():
        obj = dock.objectName()

        # docks tabificados com este
        tabbed = [d.objectName() for d in win.tabifiedDockWidgets(dock)]

        # área do dock (Qt enum)
        area = win.dockWidgetArea(dock)
        area_val = getattr(area, "value", area)

        # geometria física
        geo = dock.geometry()

        state[obj] = {
            "key": key,                         # chave lógica interna
            "title": dock.windowTitle(),        # título visível
            "visible": dock.isVisible(),        # está visível?
            "floating": dock.isFloating(),      # está solto?
            "area": int(area_val) if isinstance(area_val, (int, float)) else str(area),
            "tabbed_with": tabbed,              # docks tabificados
            "geom": [                           # posição e tamanho
                geo.x(),
                geo.y(),
                geo.width(),
                geo.height(),
            ],
        }
    return state


# ==========================================================
# MAIN
# ==========================================================
def main():
    # ------------------------------------------------------
    # Força modo offscreen (CI / headless / WSL)
    # ------------------------------------------------------
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    # Cria aplicação Qt (ou reutiliza se existir)
    app = QApplication.instance() or QApplication([])

    # Inicializa a MainWindow
    win = MainWindow()
    win.show()

    # Garante que todos os docks estão:
    # - visíveis
    # - não flutuantes
    win.ensure_all_views_visible(force_unfloat=True)

    # Estrutura base do relatório
    report = {
        "checks": {},
        "docks": {},
        "passed": True,
    }

    # ------------------------------------------------------
    # Finalização atrasada (espera layout estabilizar)
    # ------------------------------------------------------
    def finish():
        # Coleta estado completo
        state = collect_state(win)
        report["docks"] = state

        # ------------------------------
        # CHECK 1: docks em falta
        # ------------------------------
        missing = [d for d in EXPECTED_DOCKS if d not in state]

        # ------------------------------
        # CHECK 2: docks invisíveis ou sem área
        # ------------------------------
        no_area_val = getattr(Qt.NoDockWidgetArea, "value", Qt.NoDockWidgetArea)
        hidden = [
            name
            for name, s in state.items()
            if (
                not s["visible"]
                or (isinstance(s["area"], (int, float)) and s["area"] == int(no_area_val))
            )
        ]

        # ------------------------------
        # CHECK 3: docks minúsculos
        # ------------------------------
        tiny = [
            name
            for name, s in state.items()
            if s.get("geom", [0, 0, 0, 0])[2] < 40
            or s.get("geom", [0, 0, 0, 0])[3] < 40
        ]

        # Guarda resultados
        report["checks"]["missing"] = missing
        report["checks"]["hidden_or_no_area"] = hidden
        report["checks"]["tiny"] = tiny

        # Veredicto final
        report["passed"] = not missing and not hidden and not tiny

        # --------------------------------------------------
        # Escrita do relatório
        # --------------------------------------------------
        out_dir = Path("reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "layout_smoke.json"
        out_file.write_text(json.dumps(report, indent=2))

        # Output no stdout (útil para CI)
        print(
            f"layout_smoke: passed={report['passed']} "
            f"missing={missing} hidden={hidden} tiny={tiny}"
        )

        # Cleanup
        win.close()
        app.quit()

    # Espera 1.5s para garantir que Qt terminou layouting
    QTimer.singleShot(1500, finish)

    # Event loop Qt
    app.exec()


# ==========================================================
# ENTRYPOINT
# ==========================================================
if __name__ == "__main__":
    sys.exit(main())
