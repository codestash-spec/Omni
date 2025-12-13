from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QWidget


def create_dock(
    window,
    widget: QWidget,
    title: str,
    object_name: str,
    area: Qt.DockWidgetArea = Qt.LeftDockWidgetArea,
) -> QDockWidget:
    dock = QDockWidget(title, window)
    dock.setObjectName(object_name)
    dock.setWidget(widget)
    dock.setAllowedAreas(Qt.AllDockWidgetAreas)
    dock.setFeatures(
        QDockWidget.DockWidgetMovable
        | QDockWidget.DockWidgetClosable
        | QDockWidget.DockWidgetFloatable
    )
    window.addDockWidget(area, dock)
    return dock


def apply_default_layout(window, docks):
    """
    Simplified default layout: just add all docks without complex splits.
    User can arrange them as needed via drag/drop.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("  Applying simplified layout (no splits)...")
        
        # Simply add all docks to their designated areas without splitting
        # This avoids the splitDockWidget crashes
        
        docks["strategy_signals"].setFloating(False)
        window.addDockWidget(Qt.LeftDockWidgetArea, docks["strategy_signals"])
        
        docks["price_chart"].setFloating(False)
        window.addDockWidget(Qt.TopDockWidgetArea, docks["price_chart"])
        
        docks["dom_ladder"].setFloating(False)
        window.addDockWidget(Qt.RightDockWidgetArea, docks["dom_ladder"])
        
        docks["marketwatch"].setFloating(False)
        window.addDockWidget(Qt.LeftDockWidgetArea, docks["marketwatch"])
        
        docks["positions"].setFloating(False)
        window.addDockWidget(Qt.LeftDockWidgetArea, docks["positions"])
        
        docks["news"].setFloating(False)
        window.addDockWidget(Qt.LeftDockWidgetArea, docks["news"])
        
        docks["liquidity_heatmap"].setFloating(False)
        window.addDockWidget(Qt.BottomDockWidgetArea, docks["liquidity_heatmap"])
        
        docks["microstructure"].setFloating(False)
        window.addDockWidget(Qt.BottomDockWidgetArea, docks["microstructure"])
        
        docks["time_sales"].setFloating(False)
        window.addDockWidget(Qt.BottomDockWidgetArea, docks["time_sales"])
        
        docks["footprint"].setFloating(False)
        window.addDockWidget(Qt.RightDockWidgetArea, docks["footprint"])
        
        docks["volume_profile"].setFloating(False)
        window.addDockWidget(Qt.RightDockWidgetArea, docks["volume_profile"])
        
        # Show all docks by default
        for dock in docks.values():
            dock.show()
            dock.raise_()
        
        logger.info("✓ Layout applied successfully")
        
    except Exception as e:
        logger.error("CRITICAL: apply_default_layout failed: %s", e, exc_info=True)
        raise
