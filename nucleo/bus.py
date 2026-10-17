"""Bus pub/sub en memoria sobre asyncio.

- `publicar()` desde corrutinas; `publicar_desde_hilo()` desde hilos
  (lector serie, cámara), que no pueden tocar el loop directamente.
- Cada suscriptor tiene su cola acotada: si un cliente lento (pestaña del
  navegador en segundo plano) no consume, se descartan SUS eventos más
  viejos, nunca se bloquea a los productores.
- `ultimo` guarda el último valor por (refugio, tipo) para que un panel
  que se conecta tarde pinte el estado sin esperar.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable

from nucleo.evento import Evento

COLA_MAX = 512


class Bus:
    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[Evento]] = set()
        self._oyentes: list[Callable[[Evento], None]] = []
        self.ultimo: dict[tuple[str, str], Evento] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def enlazar_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publicar(self, ev: Evento) -> None:
        """Llamar solo desde el hilo del loop."""
        self.ultimo[(ev.refugio, ev.tipo)] = ev
        for q in list(self._subs):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(ev)
        for f in list(self._oyentes):
            f(ev)

    def publicar_desde_hilo(self, ev: Evento) -> None:
        if self._loop is None:
            raise RuntimeError("bus sin loop: llamar enlazar_loop() al arrancar")
        self._loop.call_soon_threadsafe(self.publicar, ev)

    def oyente(self, f: Callable[[Evento], None]) -> Callable[[], None]:
        """Callback síncrono por evento (reglas, puente serie). Devuelve
        función para darse de baja. No debe bloquear."""
        self._oyentes.append(f)
        return lambda: self._oyentes.remove(f)

    async def suscribir(self) -> AsyncIterator[Evento]:
        q: asyncio.Queue[Evento] = asyncio.Queue(maxsize=COLA_MAX)
        self._subs.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subs.discard(q)

    def estado(self) -> list[dict]:
        return [ev.to_dict() for ev in self.ultimo.values()]
