"""Confort térmico compartido: índice de calor NOAA (°C)."""
from __future__ import annotations

import math


def _c_a_f(c: float) -> float:
    return c * 9 / 5 + 32


def _f_a_c(f: float) -> float:
    return (f - 32) * 5 / 9


def indice_calor(temp_c: float, hr: float) -> float:
    """Índice de calor NOAA (°C) a partir de temperatura (°C) y HR (%).

    Fórmula simple de Steadman; si su media con T es ≥ 80 °F se usa la
    regresión de Rothfusz con los dos ajustes de NOAA (HR<13 y HR>85).
    """
    t = _c_a_f(temp_c)
    rh = hr
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    if (simple + t) / 2 < 80.0:
        return _f_a_c(simple)
    hi = (-42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh
          - 0.00683783 * t * t - 0.05481717 * rh * rh + 0.00122874 * t * t * rh
          + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh)
    if rh < 13 and 80 <= t <= 112:
        hi -= ((13 - rh) / 4) * math.sqrt((17 - abs(t - 95.0)) / 17)
    elif rh > 85 and 80 <= t <= 87:
        hi += ((rh - 85) / 10) * ((87 - t) / 5)
    return _f_a_c(hi)
