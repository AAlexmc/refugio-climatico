"""Conmutador cámara / simulación del refugio.

Cámara y pose_sim corren a la vez, pero cada una publica en un `BusFiltrado`
que solo deja pasar `pose`, `caida`, `desmayo`, `aforo` y `personas` de la fuente activa. El resto de tipos
(estado_fuente...) pasan siempre. Así el gemelo nunca recibe dos refugios y
una caída de cada fuente va sincronizada con su propio esqueleto.

Reglas (documentadas en docs):
- `pedido` = lo que quiere el usuario (arranque `--modo-inicial` o botón).
- `efectivo` = lo que se emite: "camara" solo si se pidió cámara Y llegan
  frames (salir: sin frames > SIN_FRAMES_S; entrar: último frame < ENTRADA_S).
  Si no, "sim": nunca nos quedamos sin refugio.
- Si se pidió cámara y esta cae, pasa a sim y avisa (alerta info). Vuelve
  sola a cámara cuando recupera frames. Si se pidió sim, jamás vuelve sola.
"""
from __future__ import annotations

import asyncio
import time

from nucleo.bus import Bus
from nucleo.evento import Evento, alerta

SIN_FRAMES_S = 5.0     # sin frames más de esto => cámara no disponible
ENTRADA_S = 1.5        # para (re)entrar en cámara el último frame debe ser así de reciente
GRACIA_S = 5.0         # tras arrancar, no avisar antes (la cámara tarda en abrir)
PERIODO_S = 0.5
FILTRADOS = ("pose", "caida", "desmayo", "aforo", "personas")


class BusFiltrado:
    def __init__(self, bus: Bus, ctl: "Conmutador", rol: str) -> None:
        self._bus, self._ctl, self._rol = bus, ctl, rol

    def publicar(self, ev: Evento) -> None:
        if self._ctl._deja_pasar(self._rol, ev):
            self._bus.publicar(ev)

    def publicar_desde_hilo(self, ev: Evento) -> None:
        # el filtro (y el conteo de frames) corre en el loop, no en el hilo de la cámara
        loop = self._bus._loop
        if loop is None:
            raise RuntimeError("bus sin loop: llamar enlazar_loop() al arrancar")
        loop.call_soon_threadsafe(lambda: self.publicar(ev))

    def __getattr__(self, nombre):      # oyente, enlazar_loop, suscribir...
        return getattr(self._bus, nombre)


class Conmutador:
    def __init__(self, bus: Bus, camara, sim, *, pedido: str = "camara",
                 reloj=time.monotonic, gracia_s: float | None = None) -> None:
        if pedido not in ("camara", "sim"):
            raise ValueError("modo: camara | sim")
        self.bus, self.camara, self.sim = bus, camara, sim
        self.pedido = pedido
        self.efectivo = "sim"              # hasta ver frames de cámara
        self.refugio = getattr(sim, "refugio", "R1")
        self._reloj = reloj
        self._t0 = reloj()
        self._gracia = GRACIA_S if gracia_s is None else gracia_s
        self._t_frame: float | None = None
        self._sana = False
        self._avisado = False
        self._pub: tuple | None = None

    def proxy(self, rol: str) -> BusFiltrado:
        return BusFiltrado(self.bus, self, rol)

    def _deja_pasar(self, rol: str, ev: Evento) -> bool:
        if rol == "camara" and ev.tipo == "pose":
            self._t_frame = self._reloj()     # cuenta como frame aunque esté filtrado
        if ev.tipo in FILTRADOS:
            return rol == self.efectivo
        return True

    # -- estado --------------------------------------------------------
    def estado(self) -> dict:
        return {"modo": self.efectivo, "pedido": self.pedido,
                "auto": self.pedido == "camara" and self.efectivo == "sim",
                "camara_ok": self._sana, "conmutable": True}

    def pedir(self, modo: str) -> dict:
        if modo not in ("camara", "sim"):
            raise ValueError("modo: camara | sim")
        self.pedido = modo
        self.evaluar()
        return self.estado()

    def iniciar(self) -> None:
        self._publicar_modo()

    def evaluar(self) -> None:
        """Llamar desde el hilo del loop. Decide el modo efectivo y avisa."""
        ahora = self._reloj()
        edad = float("inf") if self._t_frame is None else ahora - self._t_frame
        self._sana = edad <= (SIN_FRAMES_S if self.efectivo == "camara" else ENTRADA_S)
        nuevo = "camara" if self.pedido == "camara" and self._sana else "sim"
        if nuevo != self.efectivo:
            self.efectivo = nuevo
            self._sincronizar_caida()
        if self.pedido == "camara":
            if self.efectivo == "sim" and not self._avisado and ahora - self._t0 >= self._gracia:
                self._avisado = True
                self.bus.publicar(alerta("info", "camara", "Cámara no disponible: modo simulación",
                                         refugio=self.refugio))
            elif self.efectivo == "camara" and self._avisado:
                self._avisado = False
                self.bus.publicar(alerta("info", "camara", "Cámara recuperada: modo cámara",
                                         refugio=self.refugio))
        self._publicar_modo()

    def _sincronizar_caida(self) -> None:
        """Al cambiar de fuente, el estado de caída del bus pasa a ser el de la nueva."""
        activa = self.camara if self.efectivo == "camara" else self.sim
        quiere = bool(activa.caida)
        previo = self.bus.ultimo.get((self.refugio, "caida"))
        if quiere != bool(previo.valor if previo else False):
            self.bus.publicar(Evento("caida", quiere, "panel", self.refugio))

    def _publicar_modo(self) -> None:
        e = self.estado()
        clave = (e["modo"], e["pedido"], e["auto"], e["camara_ok"])
        if clave != self._pub:
            self._pub = clave
            self.bus.publicar(Evento("modo_pose", e, "panel", self.refugio))

    async def vigilar(self) -> None:
        self.iniciar()
        while True:
            self.evaluar()
            await asyncio.sleep(PERIODO_S)
