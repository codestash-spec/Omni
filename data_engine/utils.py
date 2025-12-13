import numpy as np


def clamp_prices(values, band: float = 0.6):
    """
    Clamp a price series to a median-based band.
    Keeps values within [median*(1-band/2), median*(1+band/2)].
    """
    arr = np.array(values, dtype=float)
    if arr.size == 0:
        return None, None
    median = float(np.median(arr))
    lower = median * (1 - band / 2)
    upper = median * (1 + band / 2)
    return lower, upper
