"""Pose sintética: esqueleto de 33 puntos MediaPipe que camina por la
habitación y cada `periodo_caida` s se cae. Los puntos pasan por el mismo
`DetectorCaidas` que la cámara real, así se prueba la cadena completa.

Ciclo (tiempo simulado): camina `periodo_caida` s -> cae (T_CAIDA) -> tumbado
(T_SUELO) -> se levanta (T_LEVANTAR) -> vuelve a caminar. Determinista con
`semilla` (solo fija las fases de la trayectoria).
"""
from __future__ import annotations

import asyncio
import math
import random

from vision.caidas import DetectorCaidas, cadera_z
from nucleo.bus import Bus
from nucleo.evento import Evento

T_CAIDA = 0.6
T_SUELO = 8.0
T_LEVANTAR = 1.0
X_RANGO = (-0.8, 0.6)   # sobre la alfombra del gemelo, lejos de cama y ventilador
Y_RANGO = (1.1, 2.4)
VEL_CAMINAR = 0.5          # rad/s de la trayectoria Lissajous (~0,5 m/s)
GROSOR_CUERPO = 0.10       # m: elevación del cuerpo tumbado

# (lateral, adelante, arriba) en metros, persona de ~1,70 m, mirando "adelante".
# Lateral + = lado izquierdo de la persona.
_N = 33
_L = {i: (0.0, 0.0, 0.0) for i in range(_N)}
_L.update({
    0: (0, .08, 1.60),
    1: (.03, .07, 1.63), 2: (.05, .07, 1.63), 3: (.07, .06, 1.63),
    4: (-.03, .07, 1.63), 5: (-.05, .07, 1.63), 6: (-.07, .06, 1.63),
    7: (.09, 0, 1.61), 8: (-.09, 0, 1.61),
    9: (.02, .07, 1.56), 10: (-.02, .07, 1.56),
    11: (.19, 0, 1.42), 12: (-.19, 0, 1.42),
    13: (.25, 0, 1.15), 14: (-.25, 0, 1.15),
    15: (.28, 0, 0.88), 16: (-.28, 0, 0.88),
    17: (.29, 0, 0.80), 18: (-.29, 0, 0.80),
    19: (.28, .03, 0.80), 20: (-.28, .03, 0.80),
    21: (.27, .03, 0.84), 22: (-.27, .03, 0.84),
    23: (.10, 0, 0.93), 24: (-.10, 0, 0.93),
    25: (.10, 0, 0.50), 26: (-.10, 0, 0.50),
    27: (.10, 0, 0.08), 28: (-.10, 0, 0.08),
    29: (.10, -.05, 0.03), 30: (-.10, -.05, 0.03),
    31: (.10, .12, 0.03), 32: (-.10, .12, 0.03),
})
_PIERNA_I = (25, 27, 29, 31)
_PIERNA_D = (26, 28, 30, 32)
_BRAZO_I = (13, 15, 17, 19, 21)
_BRAZO_D = (14, 16, 18, 20, 22)


def esqueleto(pos: tuple[float, float], rumbo: float, inclinacion: float,
              fase_paso: float = 0.0) -> list[list[float]]:
    """33 puntos [x,y,z] marco habitación.

    rumbo: dirección horizontal (rad, 0 = +y). inclinacion: 0 de pie, pi/2
    tumbado boca abajo hacia delante, rotando en torno a los pies.
    """
    fx, fy = -math.sin(rumbo), math.cos(rumbo)     # adelante horizontal
    lx, ly = -math.cos(rumbo), -math.sin(rumbo)    # izquierda de la persona (adelante × z)
    s, c = math.sin(inclinacion), math.cos(inclinacion)
    paso = math.sin(fase_paso) * 0.15 * c
    pts = []
    for i in range(_N):
        lat, ade, arr = _L[i]
        if i in _PIERNA_I or i in _BRAZO_D:
            ade += paso
        elif i in _PIERNA_D or i in _BRAZO_I:
            ade -= paso
        h = ade * c + arr * s                      # componente horizontal a lo largo de "adelante"
        z = -ade * s + arr * c + GROSOR_CUERPO * s
        pts.append([pos[0] + lat * lx + h * fx, pos[1] + lat * ly + h * fy, max(0.0, z)])
    return pts


class FuentePoseSim:
    def __init__(self, *, periodo_caida: float = 40.0, fps: int = 10, semilla: int = 0,
                 velocidad: float = 1.0, refugio: str = "R1") -> None:
        self.periodo_caida = periodo_caida
        self.fps = fps
        self.velocidad = velocidad   # segundos simulados por segundo real (tests: >1)
        self.refugio = refugio
        rng = random.Random(semilla)
        self._ph = (rng.uniform(0, 2 * math.pi), rng.uniform(0, 2 * math.pi))
        self._detector = DetectorCaidas()
        self._t = 0.0

    @property
    def caida(self) -> bool:
        return self._detector.caida

    def _ciclo(self) -> float:
        return self.periodo_caida + T_CAIDA + T_SUELO + T_LEVANTAR

    def forzar(self, caida: bool) -> None:
        """Botón de demo del panel: caer ya (True) o levantarse ya (False),
        para que el avatar coincida con la alerta."""
        n, f = divmod(self._t, self._ciclo())
        if caida and f < self.periodo_caida:
            self._t = n * self._ciclo() + self.periodo_caida
        elif not caida and f >= self.periodo_caida:
            self._t = (n + 1) * self._ciclo()

    def _oir(self, ev: Evento) -> None:
        if ev.tipo == "caida" and ev.fuente != "sim" and ev.refugio == self.refugio:
            self.forzar(bool(ev.valor))

    def _pos(self, tw: float) -> tuple[float, float, float]:
        a = tw * VEL_CAMINAR
        cx, cy = sum(X_RANGO) / 2, sum(Y_RANGO) / 2
        rx, ry = (X_RANGO[1] - X_RANGO[0]) / 2, (Y_RANGO[1] - Y_RANGO[0]) / 2
        x = cx + rx * math.sin(a + self._ph[0])
        y = cy + ry * math.sin(0.73 * a + self._ph[1])
        vx = rx * math.cos(a + self._ph[0])
        vy = ry * 0.73 * math.cos(0.73 * a + self._ph[1])
        return x, y, math.atan2(-vx, vy)   # rumbo 0 = +y

    def puntos(self, t: float) -> list[list[float]]:
        """Esqueleto en el instante simulado t (s). Ciclo periódico."""
        n, f = divmod(t, self._ciclo())
        tw = n * self.periodo_caida + min(f, self.periodo_caida)
        x, y, rumbo = self._pos(tw)
        if f < self.periodo_caida:
            bob = 0.01 * math.sin(tw * 6)
            p = esqueleto((x, y), rumbo, 0.0, fase_paso=tw * 5)
            return [[a, b, z + bob] for a, b, z in p]
        g = f - self.periodo_caida
        if g < T_CAIDA:
            incl = (math.pi / 2) * (g / T_CAIDA) ** 2          # acelera como una caída
        elif g < T_CAIDA + T_SUELO:
            incl = math.pi / 2
        else:
            u = (g - T_CAIDA - T_SUELO) / T_LEVANTAR
            incl = (math.pi / 2) * (1 - u) ** 2 * (1 if u < 1 else 0)
        return esqueleto((x, y), rumbo, incl)

    def paso(self, t: float) -> list[Evento]:
        """Eventos del instante simulado t: siempre `pose`, `caida` solo si cambia."""
        pts = self.puntos(t)
        evs = [Evento("pose", {"puntos": pts, "cadera_z": float(cadera_z(pts)), "visible": True},
                      "sim", self.refugio)]
        cambio = self._detector.actualizar(t, pts)
        if cambio is not None:
            evs.append(Evento("caida", cambio, "sim", self.refugio))
        return evs

    async def correr(self, bus: Bus) -> None:
        bus.publicar(Evento("estado_fuente", {"conectada": True, "detalle": "pose sintética"},
                            "sim", self.refugio))
        baja = bus.oyente(self._oir)
        try:
            while True:
                for ev in self.paso(self._t):
                    bus.publicar(ev)
                await asyncio.sleep(1.0 / self.fps)
                self._t += self.velocidad / self.fps
        finally:
            baja()
