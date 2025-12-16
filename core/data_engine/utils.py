import numpy as np


def clamp_prices(values, band: float = 0.6):
    """
    Clamp de preços baseado na mediana.

    Objetivo:
    - Remover outliers extremos de uma série de preços
    - Preservar a estrutura principal do mercado
    - Evitar distorções visuais e estatísticas (ex: wicks absurdos, spikes)

    Lógica:
    - Calcula a mediana da série
    - Define uma banda simétrica em torno da mediana
    - Retorna os limites inferior e superior

    Intervalo resultante:
        [ median * (1 - band/2), median * (1 + band/2) ]

    Exemplo:
        median = 100
        band = 0.6
        => lower = 70
        => upper = 130

    :param values: iterable de preços (list, np.array, etc.)
    :param band: largura relativa da banda (0.6 = ±30%)
    :return: (lower_bound, upper_bound) ou (None, None) se vazio
    """

    # Converter entrada para array numpy de floats
    arr = np.array(values, dtype=float)

    # Caso não existam valores, não há nada para filtrar
    if arr.size == 0:
        return None, None

    # Mediana é mais robusta que média contra outliers
    median = float(np.median(arr))

    # Limite inferior da banda
    lower = median * (1 - band / 2)

    # Limite superior da banda
    upper = median * (1 + band / 2)

    # Retornar apenas os limites (filtragem acontece fora)
    return lower, upper
