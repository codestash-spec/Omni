from dataclasses import dataclass
from typing import List, Tuple

# Modelos base (tipos de dados puros)
from core.data_engine.models import Candle, Trade, OrderBookSnapshot


# ============================================================
# Estado global (Symbol / Timeframe)
# ============================================================

@dataclass
class SymbolChanged:
    """
    Evento emitido quando o símbolo ativo muda.

    Consumido por:
    - ChartPanel
    - MarketWatchPanel
    - Footprint / VolumeProfile / DOM
    - Qualquer módulo que dependa do contexto de símbolo
    """
    symbol: str


@dataclass
class TimeframeChanged:
    """
    Evento emitido quando o timeframe ativo muda.

    Consumido por:
    - ChartPanel
    - VolumeProfile
    - Footprint
    - Engines de agregação temporal
    """
    timeframe: str


# ============================================================
# Candles (OHLCV)
# ============================================================

@dataclass
class CandleHistory:
    """
    Evento de envio de histórico completo de candles.

    Emitido tipicamente:
    - após mudança de símbolo
    - após mudança de timeframe
    - na inicialização do engine

    Substitui qualquer histórico anterior.
    """
    symbol: str
    timeframe: str
    candles: List[Candle]


@dataclass
class CandleUpdate:
    """
    Evento incremental de candle.

    Pode representar:
    - atualização do candle em formação (closed=False)
    - fecho definitivo de um candle (closed=True)

    Permite updates eficientes sem recarregar histórico completo.
    """
    symbol: str
    timeframe: str
    candle: Candle
    closed: bool


# ============================================================
# Trades (Time & Sales)
# ============================================================

@dataclass
class TradeEvent:
    """
    Evento unitário de trade (Time & Sales).

    Emitido em tempo real pelo engine de mercado.
    Consumido por:
    - TapePanel
    - Footprint
    - VolumeProfile
    - Microstructure
    """
    trade: Trade


# ============================================================
# Order Book / Depth (DOM)
# ============================================================

@dataclass
class DepthSnapshotEvent:
    """
    Snapshot completo do livro de ordens.

    Emitido:
    - na subscrição inicial
    - após resync
    - quando necessário garantir consistência

    bids / asks:
    - Listas de tuples (price, size)
    - Já normalizadas e filtradas
    """
    symbol: str
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]
    last_update_id: int


@dataclass
class DepthUpdateEvent:
    """
    Update incremental do livro de ordens.

    Contém apenas níveis alterados desde o último snapshot.
    """
    symbol: str
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]
    last_update_id: int


# ============================================================
# Tickers / Market Watch
# ============================================================

@dataclass
class TickersEvent:
    """
    Evento agregado de tickers.

    Normalmente contém:
    - Lista completa de símbolos observados
    - Dados de 24h (last, %change, volume, bid, ask)

    Consumido por:
    - MarketWatchPanel
    - Verificação externa (verify_suite)
    """
    tickers: list
