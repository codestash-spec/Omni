from PySide6.QtGui import QFont


def inter(point_size: int, weight: int = QFont.Medium) -> QFont:
    font = QFont("Inter")
    font.setPointSize(point_size)
    font.setWeight(weight)
    return font


def mono(point_size: int, weight: int = QFont.DemiBold) -> QFont:
    font = QFont("JetBrains Mono")
    font.setPointSize(point_size)
    font.setWeight(weight)
    return font
