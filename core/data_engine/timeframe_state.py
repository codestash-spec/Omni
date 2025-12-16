import threading


class TimeframeState:
    """
    Estado thread-safe para gerir o timeframe atual da aplicação.

    Responsabilidades:
    - Armazenar o timeframe ativo (ex: "1m", "5m", "1h")
    - Garantir acesso seguro em ambientes multi-thread
    - Evitar condições de corrida entre UI, engine e feeds de dados

    Nota:
    - Não emite sinais
    - Apenas mantém estado sincronizado
    - Ideal para ser usado por CoreDataEngine, ChartEngine, etc.
    """

    def __init__(self, initial_timeframe: str = "1m"):
        # Lock para garantir acesso atómico ao timeframe
        self._lock = threading.Lock()

        # Timeframe atual (sempre armazenado em lowercase)
        self._timeframe = initial_timeframe

    @property
    def timeframe(self) -> str:
        """
        Getter thread-safe do timeframe atual.

        :return: timeframe atual (ex: "1m")
        """
        with self._lock:
            return self._timeframe

    def set(self, timeframe: str) -> str:
        """
        Atualiza o timeframe de forma thread-safe.

        Comportamento:
        - Normaliza o valor para lowercase
        - Se for igual ao atual, não faz nada
        - Caso contrário, atualiza e devolve o novo valor

        :param timeframe: novo timeframe (ex: "5m", "1H", etc.)
        :return: timeframe efetivamente ativo após a chamada
        """
        tf = timeframe.lower()

        with self._lock:
            # Evita escrita desnecessária se não houver mudança
            if tf == self._timeframe:
                return self._timeframe

            # Atualiza o estado interno
            self._timeframe = tf
            return self._timeframe
