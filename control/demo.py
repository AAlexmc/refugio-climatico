"""Director de la demo guiada: publica el guion y los eventos de cada paso.

El clima (temp_ext) y el aforo los pone el simulador; aquí solo se narra y se
inyecta lo que el sim no hace solo (desmayo, comando «atendido»).
"""
from __future__ import annotations

import asyncio

from nucleo.bus import Bus
from nucleo.evento import Evento

# (título, texto, espera en s a escala 1)
PASOS = [
    ("Ola de calor", "Fuera hace calor extremo: el refugio mantiene el interior habitable.", 8),
    ("Llega el autobús", "Aforo 12 personas: la cámara cuenta cuánta gente hay dentro.", 8),
    ("Refuerzo térmico", "Más gente, más calor: las reglas encienden ventilador y aire acondicionado.", 8),
    ("Desmayo", "Una persona se queda inmóvil en el suelo: la visión detecta el desmayo.", 10),
    ("Aviso al 061", "Alerta crítica enviada al 061 con la ubicación del refugio y el nº de personas dentro.", 8),
    ("Atendido", "Los sanitarios atienden a la persona: la alerta se resuelve.", 6),
    ("Resultado", "Resultados medidos del refugio: ver /metricas.html", 10),
]


class Director:
    def __init__(self, bus: Bus) -> None:
        self.bus = bus
        self._tarea: asyncio.Task | None = None

    @property
    def activa(self) -> bool:
        return self._tarea is not None and not self._tarea.done()

    def iniciar(self, escala: float = 1.0) -> None:
        self.parar(avisar=False)
        self._tarea = asyncio.get_running_loop().create_task(self._correr(escala), name="demo")

    def parar(self, avisar: bool = True) -> None:
        t, self._tarea = self._tarea, None
        if t is not None and not t.done():
            t.cancel()
            if avisar:
                self._guion(0, "", "")

    def _guion(self, paso: int, titulo: str, texto: str) -> None:
        self.bus.publicar(Evento("guion", {"paso": paso, "total": len(PASOS),
                                           "titulo": titulo, "texto": texto}, "panel"))

    async def _correr(self, escala: float) -> None:
        for n, (titulo, texto, espera) in enumerate(PASOS, 1):
            self._guion(n, titulo, texto)
            if n == 4:
                self.bus.publicar(Evento("desmayo", {"activo": True, "persona": 1,
                                                     "segundos_inmovil": 6, "zona": "interior"}, "panel"))
            elif n == 6:
                self.bus.publicar(Evento("comando", {"destino": "atendido", "valor": "desmayo"}, "panel"))
                self.bus.publicar(Evento("desmayo", {"activo": False}, "panel"))
            await asyncio.sleep(espera * escala)
        self._guion(0, "", "")
