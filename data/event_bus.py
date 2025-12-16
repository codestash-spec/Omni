from PySide6.QtCore import QObject, Signal

# Estado global da aplicação (símbolo atual, status, etc.)
from core.app_state import AppState


class EventBus(QObject):
    """
    EventBus central da aplicação.

    Responsabilidades:
    - Desacoplar produtores de dados (engine, providers, bots)
      dos consumidores (UI, painéis, gráficos).
    - Normalizar sinais Qt para toda a app.
    - Propagar alterações globais vindas do AppState.
    """

    # ======================================================
    # SINAIS GLOBAIS
    # ======================================================

    # Lista de tickers (MarketWatch)
    market_tickers = Signal(list)   # List[TickerData]

    # Trade individual (Time & Sales / Tape)
    trade = Signal(object)          # TradeData

    # Histórico ou update de candles
    candles = Signal(list)          # List[CandleData]

    # Status textual da aplicação (ex: "Connected", "Reconnecting")
    status = Signal(str)

    # Mudança de símbolo global (BTCUSDT, ETHUSDT, etc.)
    symbol_changed = Signal(str)

    # ======================================================
    # INIT
    # ======================================================
    def __init__(self, app_state: AppState):
        super().__init__()

        # Referência ao estado global da app
        self.app_state = app_state

        # --------------------------------------------------
        # Forward automático de eventos do AppState
        # --------------------------------------------------
        # Sempre que o AppState muda o símbolo,
        # o EventBus reemite o sinal
        self.app_state.symbol_changed.connect(self.symbol_changed.emit)

        # Sempre que o status global muda,
        # reemite para UI / status bar
        self.app_state.status_changed.connect(self.status.emit)

    # ======================================================
    # MÉTODOS DE PUBLICAÇÃO
    # ======================================================

    def publish_tickers(self, data):
        """
        Publica uma lista de tickers atualizados.

        Normalmente chamado por:
        - Market data provider
        - CoreDataEngine
        """
        self.market_tickers.emit(data)

    def publish_trade(self, trade):
        """
        Publica um trade individual.

        Consumido por:
        - Time & Sales
        - Footprint
        - Volume Profile
        - Microstructure
        """
        self.trade.emit(trade)

    def publish_candles(self, candles):
        """
        Publica histórico ou atualização de candles.

        Consumido por:
        - Price Chart
        - Volume Profile
        - Estratégias
        """
        self.candles.emit(candles)

    def publish_status(self, status: str):
        """
        Publica mensagem de status global.

        Exemplos:
        - "Connected"
        - "Disconnected"
        - "Reconnecting..."
        """
        self.status.emit(status)
