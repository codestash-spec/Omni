from collections import deque
from typing import Deque, List, Dict


class ChartEngine:
    """
    ChartEngine

    Responsabilidade:
    - Manter um buffer eficiente de candles (OHLCV)
    - Suportar updates incrementais (último candle em formação)
    - Garantir uma janela fixa (rolling window) de candles visíveis

    NOTA:
    Este motor é propositalmente simples:
    - Não faz cálculos técnicos
    - Não faz rendering
    - Apenas gere estado de candles
    """

    def __init__(self, max_candles: int = 300):
        """
        Inicializa o motor de candles.

        :param max_candles: número máximo de candles mantidos em memória
        """
        self.max_candles = max_candles

        # Deque garante:
        # - append O(1)
        # - pop automático quando atinge maxlen
        self._candles: Deque[Dict] = deque(maxlen=max_candles)

    # ======================================================
    # CARGA DE HISTÓRICO
    # ======================================================

    def set_history(self, candles: List[Dict]):
        """
        Substitui completamente o histórico atual.

        Usado quando:
        - Muda símbolo
        - Muda timeframe
        - Carregamento inicial

        Apenas os últimos `max_candles` são mantidos.
        """
        self._candles.clear()
        for c in candles[-self.max_candles :]:
            self._candles.append(c)

    # ======================================================
    # ACESSO A DADOS
    # ======================================================

    def get_visible_candles(self) -> List[Dict]:
        """
        Retorna os candles atualmente mantidos no buffer.

        Usado pelo ChartPanel para renderização.
        """
        return list(self._candles)

    # ======================================================
    # UPDATES INCREMENTAIS
    # ======================================================

    def append_candle(self, candle: Dict):
        """
        Adiciona um novo candle fechado.

        Normalmente chamado quando:
        - Um candle fecha
        - Novo período começa
        """
        self._candles.append(candle)

    def update_last_candle(self, candle: Dict):
        """
        Atualiza o último candle (em formação).

        Fluxo típico:
        - Recebe updates tick-by-tick
        - Último candle é substituído
        - Não altera candles históricos
        """
        if self._candles:
            self._candles.pop()
        self._candles.append(candle)
