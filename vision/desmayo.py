"""Desmayo = caída + persona inmóvil en el suelo durante `inmovil_s`.

Lógica pura (sin cámara): por frame recibe el tiempo, si hay caída y la
posición horizontal de la cadera. Si la cadera se mueve más de
`tolerancia_m` se reinicia la cuenta (alguien que se arrastra o se levanta
a medias no es un desmayo). Devuelve el valor del evento `desmayo` solo
cuando cambia `activo`; `segundos_inmovil` se lee en `estado()`.
"""
from __future__ import annotations

import math

INMOVIL_S = 5.0        # demo: 5 s; en producción ~15-20 s
TOLERANCIA_M = 0.15


class DetectorDesmayo:
    def __init__(self, inmovil_s: float = INMOVIL_S, tolerancia_m: float = TOLERANCIA_M,
                 zona: str = "interior") -> None:
        self.inmovil_s = inmovil_s
        self.tolerancia_m = tolerancia_m
        self.zona = zona
        self.activo = False
        self.persona: int | None = None
        self._ancla: tuple[float, float] | None = None
        self._t_ancla = 0.0
        self._t = 0.0

    def estado(self) -> dict:
        quieto = 0.0 if self._ancla is None else max(0.0, self._t - self._t_ancla)
        d = {"activo": self.activo, "segundos_inmovil": round(quieto, 1), "zona": self.zona}
        if self.persona is not None:
            d["persona"] = self.persona
        return d

    def actualizar(self, t: float, caida: bool, cadera_xy: tuple[float, float] | None,
                   persona: int | None = None) -> dict | None:
        self._t = t
        if not caida:
            self._ancla = None
            if self.activo:
                self.activo = False
                return self.estado()
            return None
        if cadera_xy is not None:
            if self._ancla is None or math.dist(cadera_xy, self._ancla) > self.tolerancia_m:
                self._ancla, self._t_ancla = tuple(cadera_xy), t
        elif self._ancla is None:          # caída sin posición: contar desde ya
            self._ancla, self._t_ancla = (0.0, 0.0), t
        if persona is not None:
            self.persona = persona
        if not self.activo and t - self._t_ancla >= self.inmovil_s:
            self.activo = True
            return self.estado()
        return None


def cadera_xy(puntos) -> tuple[float, float]:
    return ((puntos[23][0] + puntos[24][0]) / 2, (puntos[23][1] + puntos[24][1]) / 2)
