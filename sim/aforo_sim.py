"""Aforo simulado: gente que entra y sale (llegadas de autobús = picos).

Se sustituye por `vision.aforo:FuenteAforo` (cámara real, Ordenador 1).
Un `aforo` inyectado por otra fuente (botón del panel, /api/evento) fija el
valor actual y la simulación sigue desde ahí.
"""
from __future__ import annotations

import asyncio
import random

from nucleo.bus import Bus
from nucleo.evento import Evento


class FuenteAforoSim:
    def __init__(self, maximo: int = 20, periodo: float = 2.0, semilla: int | None = None,
                 refugio: str = "R1") -> None:
        self.maximo = maximo
        self.periodo = periodo
        self.refugio = refugio
        self.n = 3
        self.rng = random.Random(semilla)

    def _oir(self, ev: Evento) -> None:
        if ev.tipo == "aforo" and ev.fuente != "sim" and ev.refugio == self.refugio:
            self.n = int(ev.valor)

    def paso(self) -> int:
        if self.rng.random() < 0.05:                       # llega un bus
            self.n += self.rng.randint(4, 10)
        self.n += self.rng.choice((-1, -1, 0, 0, 1))
        self.n = min(max(self.n, 0), int(self.maximo * 1.3))
        return self.n

    async def correr(self, bus: Bus) -> None:
        baja = bus.oyente(self._oir)
        try:
            while True:
                bus.publicar(Evento("aforo", self.paso(), "sim", self.refugio))
                await asyncio.sleep(self.periodo)
        finally:
            baja()
