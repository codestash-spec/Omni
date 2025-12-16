from collections import deque
from typing import Deque, Dict, List, Tuple

from core.data_engine.models import Candle, Trade


class CacheManager:
    """
    CACHE MANAGER (IN-MEMORY)

    Responsável por manter um cache local e rápido de:
    - Candles (por símbolo + timeframe)
    - Trades (por símbolo)
    - Order Book (depth snapshot)

    Objetivos:
    - Reduzir dependência direta do provider
    - Permitir replay / acesso rápido aos dados
    - Servir de base para persistência futura (disk / DB)

    NOTA:
    - Atualmente é apenas RAM-based
    - Estrutura já preparada para evolução
    """

    def __init__(self, max_candles: int = 1200, max_trades: int = 2000):
        """
        Inicializa o cache com limites fixos.

        max_candles:
            Número máximo de candles mantidos por (symbol, timeframe)

        max_trades:
            Número máximo de trades mantidos por símbolo
        """
        self._max_candles = max_candles
        self._max_trades = max_trades

        # Candles indexados por (SYMBOL, TIMEFRAME)
        self._candles: Dict[Tuple[str, str], Deque[Candle]] = {}

        # Trades indexados apenas por SYMBOL
        self._trades: Dict[str, Deque[Trade]] = {}

        # Depth snapshot por SYMBOL
        # Estrutura simples (último estado conhecido)
        self._depth: Dict[str, Dict] = {}

    # ============================================================
    # Candle cache
    # ============================================================

    def set_history(self, symbol: str, timeframe: str, candles: List[Candle]):
        """
        Substitui completamente o histórico de candles
        para um símbolo + timeframe.

        Usado tipicamente após:
        - request inicial de histórico
        - mudança de símbolo
        - mudança de timeframe
        """
        key = (symbol.upper(), timeframe)

        dq: Deque[Candle] = deque(maxlen=self._max_candles)
        for c in candles[-self._max_candles :]:
            dq.append(c)

        self._candles[key] = dq

    def append_candle(self, symbol: str, timeframe: str, candle: Candle, closed: bool):
        """
        Atualiza incrementalmente candles.

        Regras:
        - Se candle estiver fechado → append ou replace
        - Se candle estiver em formação → replace último
        """
        key = (symbol.upper(), timeframe)
        dq = self._candles.get(key)

        if not dq:
            dq = deque(maxlen=self._max_candles)
            self._candles[key] = dq

        if closed:
            # Candle fechado → append se novo, replace se overlap
            if dq and candle.open_time <= dq[-1].open_time:
                dq[-1] = candle
            else:
                dq.append(candle)
        else:
            # Candle ainda em formação → atualizar último
            if dq:
                dq[-1] = candle
            else:
                dq.append(candle)

    def get_history(self, symbol: str, timeframe: str) -> List[Candle]:
        """
        Retorna lista de candles em cache para símbolo + timeframe.
        """
        key = (symbol.upper(), timeframe)
        if key not in self._candles:
            return []
        return list(self._candles[key])

    # ============================================================
    # Trades cache
    # ============================================================

    def append_trade(self, symbol: str, trade: Trade):
        """
        Adiciona trade ao cache de Time & Sales.

        Cache é:
        - por símbolo
        - limitado por max_trades
        """
        key = symbol.upper()
        dq = self._trades.get(key)

        if not dq:
            dq = deque(maxlen=self._max_trades)
            self._trades[key] = dq

        dq.append(trade)

    def get_trades(self, symbol: str) -> List[Trade]:
        """
        Retorna trades recentes de um símbolo.
        """
        key = symbol.upper()
        if key not in self._trades:
            return []
        return list(self._trades[key])

    # ============================================================
    # Depth / Order Book cache
    # ============================================================

    def set_depth(
        self,
        symbol: str,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        last_update_id: int,
    ):
        """
        Atualiza snapshot do order book.

        Estrutura mantida simples:
        - bids
        - asks
        - last_update_id (para sincronização futura)
        """
        self._depth[symbol.upper()] = {
            "bids": bids,
            "asks": asks,
            "last_update_id": last_update_id,
        }

    def get_depth(self, symbol: str):
        """
        Retorna último snapshot de depth para o símbolo.
        """
        return self._depth.get(symbol.upper())
