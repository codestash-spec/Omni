import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


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


def collect_state(win: MainWindow):
    state = {}
    for key, dock in win.docks.items():
        obj = dock.objectName()
        tabbed = [d.objectName() for d in win.tabifiedDockWidgets(dock)]
        area = win.dockWidgetArea(dock)
        area_val = getattr(area, "value", area)
        geo = dock.geometry()
        state[obj] = {
            "key": key,
            "title": dock.windowTitle(),
            "visible": dock.isVisible(),
            "floating": dock.isFloating(),
            "area": int(area_val) if isinstance(area_val, (int, float)) else str(area),
            "tabbed_with": tabbed,
            "geom": [geo.x(), geo.y(), geo.width(), geo.height()],
        }
    return state


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    win.show()
    win.ensure_all_views_visible(force_unfloat=True)

    report = {"checks": {}, "docks": {}, "passed": True}

    def finish():
        state = collect_state(win)
        report["docks"] = state

        missing = [d for d in EXPECTED_DOCKS if d not in state]
        no_area_val = getattr(Qt.NoDockWidgetArea, "value", Qt.NoDockWidgetArea)
        hidden = [
            name
            for name, s in state.items()
            if (not s["visible"]) or (isinstance(s["area"], (int, float)) and s["area"] == int(no_area_val))
        ]
        tiny = [name for name, s in state.items() if s.get("geom", [0, 0, 0, 0])[2] < 40 or s.get("geom", [0, 0, 0, 0])[3] < 40]

        report["checks"]["missing"] = missing
        report["checks"]["hidden_or_no_area"] = hidden
        report["checks"]["tiny"] = tiny
        report["passed"] = not missing and not hidden and not tiny

        out_dir = Path("reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "layout_smoke.json"
        out_file.write_text(json.dumps(report, indent=2))
        print(f"layout_smoke: passed={report['passed']} missing={missing} hidden={hidden} tiny={tiny}")
        win.close()
        app.quit()

    QTimer.singleShot(1500, finish)
    app.exec()


if __name__ == "__main__":
    sys.exit(main())
