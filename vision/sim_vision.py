"""Visión simulada: lo mismo que publica la RealSense, sin cámara.

- `pose` + `caida` del esqueleto sintético (`vision/pose_sim.py`) = "Persona 1".
- `personas` con etiquetas: gente que entra por la puerta, va a un banco, se
  sienta un rato y se va; cada `bus_s` s llega un autobús (grupo de 3-7).
- `aforo` = nº de personas dentro (mismo `Aforo` que la cámara).
- `desmayo` con el mismo `DetectorDesmayo` que la cámara: Persona 1 cae y
  queda quieta -> desmayo activo con su id.

Un `aforo` externo (botón del panel, /api/evento) añade o quita gente hasta
ese número, así el gemelo y el contador cuentan lo mismo.
Coordenadas: marco refugio (x lateral, y fondo desde la cámara, metros).
"""
from __future__ import annotations

import asyncio
import math
import random

from nucleo.bus import Bus
from nucleo.evento import Evento
from vision.aforo import Aforo
from vision.caidas import cadera_z
from vision.desmayo import DetectorDesmayo, cadera_xy
from vision.pose_sim import FuentePoseSim

ENTRADA = (0.0, 5.5)
BANCOS = [(-2.0 + 0.6 * i, y) for y in (3.0, 4.2) for i in range(7)]   # 14 plazas sentadas
DE_PIE = [(-2.2 + 0.55 * i, 5.0) for i in range(9)]                    # 9 de pie
VEL_M_S = 0.9
ESTANCIA_S = (40.0, 160.0)


class _Persona:
    def __init__(self, id_: int, destino: tuple[float, float], hasta: float) -> None:
        self.id = id_
        self.x, self.y = ENTRADA
        self.destino = destino
        self.hasta = hasta        # instante simulado en que se va
        self.saliendo = False

    def mover(self, dt: float) -> bool:
        """Avanza hacia el destino; True si ha llegado."""
        dx, dy = self.destino[0] - self.x, self.destino[1] - self.y
        d = math.hypot(dx, dy)
        paso = VEL_M_S * dt
        if d <= paso:
            self.x, self.y = self.destino
            return True
        self.x += dx / d * paso
        self.y += dy / d * paso
        return False


class FuenteVisionSim:
    def __init__(self, *, fps: int = 10, bus_s: float = 90.0, semilla: int = 0,
                 velocidad: float = 1.0, refugio: str = "R1", inicial: int = 4,
                 periodo_caida: float = 40.0, inmovil_s: float | None = None) -> None:
        self.fps, self.bus_s, self.velocidad, self.refugio = fps, bus_s, velocidad, refugio
        self.pose = FuentePoseSim(periodo_caida=periodo_caida, fps=fps, semilla=semilla,
                                  velocidad=velocidad, refugio=refugio)
        self._desmayo = DetectorDesmayo(**({} if inmovil_s is None else {"inmovil_s": inmovil_s}))
        self._aforo = Aforo(ventana=1)
        self.rng = random.Random(semilla)
        self.gente: dict[int, _Persona] = {}
        self._sig_id = 2                       # 1 = el esqueleto de pose_sim
        self._t = 0.0
        self._sig_bus = bus_s
        for _ in range(inicial):
            self._entrar(0.0)

    # el Conmutador sincroniza el estado de caída con la fuente activa
    @property
    def caida(self) -> bool:
        return self.pose.caida

    def _plaza_libre(self) -> tuple[float, float] | None:
        ocupadas = {p.destino for p in self.gente.values() if not p.saliendo}
        libres = [s for s in BANCOS if s not in ocupadas] or [s for s in DE_PIE if s not in ocupadas]
        return self.rng.choice(libres) if libres else None

    def _entrar(self, t: float) -> bool:
        plaza = self._plaza_libre()
        if plaza is None:
            return False
        p = _Persona(self._sig_id, plaza, t + self.rng.uniform(*ESTANCIA_S))
        self.gente[p.id] = p
        self._sig_id += 1
        return True

    def _salir_uno(self) -> None:
        dentro = [p for p in self.gente.values() if not p.saliendo]
        if dentro:
            p = min(dentro, key=lambda q: q.hasta)
            p.saliendo, p.destino = True, ENTRADA

    def fijar_aforo(self, n: int) -> None:
        """Botón del panel: ajustar la gente simulada a `n` personas (incl. Persona 1)."""
        objetivo = max(0, int(n) - 1)
        while len([p for p in self.gente.values() if not p.saliendo]) < objetivo:
            if not self._entrar(self._t):
                break
        while len([p for p in self.gente.values() if not p.saliendo]) > objetivo:
            self._salir_uno()

    def _oir(self, ev: Evento) -> None:
        if ev.refugio != self.refugio or ev.fuente == "sim":
            return
        if ev.tipo == "aforo" and isinstance(ev.valor, (int, float)):
            self.fijar_aforo(int(ev.valor))
        else:
            self.pose._oir(ev)

    def _avanzar_gente(self, t: float, dt: float) -> None:
        if t >= self._sig_bus:
            for _ in range(self.rng.randint(3, 7)):
                self._entrar(t)
            self._sig_bus = t + self.bus_s * self.rng.uniform(0.7, 1.3)
        elif self.rng.random() < dt / 25.0:      # alguien que pasa y entra
            self._entrar(t)
        for p in list(self.gente.values()):
            llegado = p.mover(dt)
            if p.saliendo and llegado:
                del self.gente[p.id]
            elif not p.saliendo and t >= p.hasta:
                p.saliendo, p.destino = True, ENTRADA

    def personas(self) -> list[dict]:
        out = []
        pts = self.pose.puntos(self._t)
        x1, y1 = cadera_xy(pts)
        out.append({"id": 1, "x": round(x1, 2), "y": round(y1, 2), "etiqueta": "Persona 1",
                    "estado": "suelo" if cadera_z(pts) < 0.45 else "de_pie"})
        for p in self.gente.values():
            quieto = (p.x, p.y) == p.destino and not p.saliendo
            out.append({"id": p.id, "x": round(p.x, 2), "y": round(p.y, 2),
                        "etiqueta": f"Persona {p.id}",
                        "estado": ("sentado" if p.destino in BANCOS else "de_pie") if quieto else "de_pie"})
        return out

    def paso(self, t: float, dt: float, con_personas: bool = True) -> list[Evento]:
        self._t = t
        evs = self.pose.paso(t)
        pts = self.pose.puntos(t)
        d = self._desmayo.actualizar(t, self.pose.caida, cadera_xy(pts), 1)
        if d is not None:
            evs.append(Evento("desmayo", d, "sim", self.refugio))
        self._avanzar_gente(t, dt)
        if con_personas:
            gente = self.personas()
            evs.append(Evento("personas", gente, "sim", self.refugio))
            n = self._aforo.actualizar(t, len(gente))
            if n is not None:
                evs.append(Evento("aforo", n, "sim", self.refugio))
        return evs

    async def correr(self, bus: Bus) -> None:
        bus.publicar(Evento("estado_fuente", {"conectada": True, "detalle": "visión simulada"},
                            "sim", self.refugio))
        baja = bus.oyente(self._oir)
        dt = self.velocidad / self.fps
        k = 0
        try:
            while True:
                # personas/aforo a 2 Hz; pose a `fps`
                for ev in self.paso(self._t, dt, con_personas=k % max(1, self.fps // 2) == 0):
                    bus.publicar(ev)
                k += 1
                await asyncio.sleep(1.0 / self.fps)
                self._t += dt
        finally:
            baja()
