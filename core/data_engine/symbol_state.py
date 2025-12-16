import threading


class SymbolState:
    """
    Estado thread-safe para gerir o símbolo atualmente selecionado.

    Responsabilidades:
    - Armazenar o símbolo ativo (ex: "BTCUSDT", "ETHUSDT")
    - Garantir acesso seguro em ambientes multi-thread
    - Evitar condições de corrida entre UI, data engine e feeds externos

    Nota:
    - Não emite sinais
    - Apenas mantém estado sincronizado
    - Complementa diretamente o TimeframeState
    """

    def __init__(self, initial_symbol: str = "BTCUSDT"):
        # Lock para garantir acesso atómico ao símbolo
        self._lock = threading.Lock()

        # Símbolo atual (normalizado para uppercase)
        self._symbol = initial_symbol.upper()

    @property
    def symbol(self) -> str:
        """
        Getter thread-safe do símbolo atual.

        :return: símbolo ativo (ex: "BTCUSDT")
        """
        with self._lock:
            return self._symbol

    def set(self, symbol: str) -> str:
        """
        Atualiza o símbolo de forma thread-safe.

        Comportamento:
        - Normaliza o símbolo para uppercase
        - Se for igual ao atual, não faz nada
        - Caso contrário, atualiza e devolve o novo símbolo

        :param symbol: novo símbolo (ex: "ethusdt", "BTCUSD")
        :return: símbolo efetivamente ativo após a chamada
        """
        symbol = symbol.upper()

        with self._lock:
            # Evita escrita desnecessária se não houver mudança
            if symbol == self._symbol:
                return self._symbol

            # Atualiza o estado interno
            self._symbol = symbol
            return self._symbol
