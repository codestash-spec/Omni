from PySide6.QtCore import QObject, Signal


class AppState(QObject):
    """
    AppState

    Responsabilidade:
    - Manter o estado global mínimo da aplicação
    - Centralizar mudanças de símbolo e estado de conexão
    - Emitir sinais para sincronizar UI + DataEngine

    Este objeto funciona como:
    - Single Source of Truth (leve)
    - Store reativa (Qt-style)
    """

    # Emitido sempre que o símbolo ativo muda
    symbol_changed = Signal(str)

    # Emitido sempre que o estado de ligação muda
    status_changed = Signal(str)

    def __init__(self, initial_symbol: str = "BTCUSDT", asset_class: str = "Crypto"):
        """
        Inicializa o estado global da aplicação.

        :param initial_symbol: símbolo inicial (ex: BTCUSDT)
        :param asset_class: classe de ativo (Crypto, Futures, FX, etc.)
        """
        super().__init__()

        # Símbolo atualmente selecionado (sempre em uppercase)
        self.current_symbol = initial_symbol.upper()

        # Classe de ativo ativa (usado por UI / providers)
        self.asset_class = asset_class

        # Estado da ligação aos providers (ex: connected / disconnected)
        self.connection_status = "disconnected"

    # ======================================================
    # SÍMBOLO ATIVO
    # ======================================================

    def set_symbol(self, symbol: str):
        """
        Atualiza o símbolo ativo da aplicação.

        - Normaliza para uppercase
        - Evita emissões redundantes
        - Notifica todos os listeners (MarketWatch, Chart, Engines, etc.)
        """
        symbol = symbol.upper()
        if symbol != self.current_symbol:
            self.current_symbol = symbol
            self.symbol_changed.emit(symbol)

    # ======================================================
    # ESTADO DE CONEXÃO
    # ======================================================

    def set_status(self, status: str):
        """
        Atualiza o estado de conexão global.

        Exemplos:
        - "connecting"
        - "connected"
        - "disconnected"
        - "error"

        Apenas emite sinal se houver mudança real.
        """
        if status != self.connection_status:
            self.connection_status = status
            self.status_changed.emit(status)
