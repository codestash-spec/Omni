from dataclasses import dataclass
from typing import List


# ============================================================
# Ticker / Market Summary
# ============================================================

@dataclass
class TickerData:
    """
    Representa o estado resumido de um mercado (ticker).

    Usado principalmente em:
    - MarketWatchPanel
    - Atualizações rápidas de preço
    - Verificação de consistência (verify_suite)

    Todos os valores são esperados em formato FLOAT já normalizado.
    """
    symbol: str              # Ex: "BTCUSDT"
    last_price: float        # Último preço negociado
    pct_change: float        # Variação percentual (24h)
    volume: float            # Volume total (base asset)
    bid: float               # Melhor bid atual
    ask: float               # Melhor ask atual

    @property
    def spread(self) -> float:
        """
        Spread calculado dinamicamente.

        Garantia:
        - Nunca devolve valores negativos
        """
        return max(0.0, self.ask - self.bid)


# ============================================================
# Candle / OHLCV
# ============================================================

@dataclass
class Candle:
    """
    Representa um candle OHLCV padrão.

    Usado em:
    - ChartPanel
    - VolumeProfile
    - Footprint
    - Verificação REST (klines)

    Notas:
    - open_time é sempre em milissegundos (epoch ms)
    - Não contém símbolo para permitir reutilização por contexto
    """
    open_time: int  # Timestamp de abertura do candle (ms)
    open: float
    high: float
    low: float
    close: float
    volume: float


# ============================================================
# Trade / Time & Sales
# ============================================================

@dataclass
class Trade:
    """
    Representa uma trade individual (Time & Sales).

    Usado em:
    - TapePanel
    - Footprint
    - VolumeProfile
    - Microstructure
    - Verificação de trades (aggTrades)

    Convenções:
    - side deve ser "Buy" ou "Sell"
    - ts em milissegundos (epoch ms)
    """
    symbol: str      # Ex: "BTCUSDT"
    price: float     # Preço executado
    qty: float       # Quantidade (base asset)
    side: str        # "Buy" ou "Sell"
    ts: int          # Timestamp da trade (ms)


# ============================================================
# Order Book / DOM
# ============================================================

@dataclass
class OrderBookLevel:
    """
    Nível individual do livro de ordens.

    Usado tanto para bids como asks.
    """
    price: float     # Preço do nível
    size: float      # Quantidade disponível


@dataclass
class OrderBookSnapshot:
    """
    Snapshot completo do livro de ordens.

    Usado em:
    - DOM Ladder
    - Heatmap
    - Verificação de depth REST

    Nota:
    - bids e asks devem vir já ordenados externamente
    """
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    ts: int          # Timestamp do snapshot (ms)
