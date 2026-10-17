"""Detector de caídas: lógica pura, sin cámara.

Entrada por frame: tiempo (s) y los 33 puntos MediaPipe en marco habitación
(z hacia arriba, metros), o None si no hay persona. Salida: True/False solo
cuando cambia el estado de caída, None si no cambia.

Secuencia: descenso rápido de la cadera -> cadera baja + torso casi
horizontal sostenido -> caída. Tumbarse despacio nunca arma el detector.
Levantarse: cadera alta sostenida.
"""
from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

# Índices MediaPipe Pose
HOMBRO_I, HOMBRO_D = 11, 12
CADERA_I, CADERA_D = 23, 24

VEL_DESCENSO = -1.0        # m/s: velocidad vertical de cadera que arma el detector
VENTANA_VEL = 0.5          # s: tramo sobre el que se mide la velocidad
VENTANA_CAIDA = 1.0        # s: ventana para medir la caída relativa
CAIDA_RELATIVA = 0.40      # fracción de la altura de cadera perdida en VENTANA_CAIDA
ARMADO_S = 3.0             # s que dura "armado" tras un descenso rápido
CADERA_SUELO = 0.45        # m: por debajo = en el suelo
ANGULO_TORSO = 60.0        # grados respecto a la vertical: por encima = horizontal
SUELO_SOSTENIDO_S = 1.0    # s con cadera baja + torso horizontal => caída
CADERA_LEVANTADO = 0.70    # m
LEVANTADO_SOSTENIDO_S = 2.0
MIN_DT_VEL = 0.2           # s mínimos entre muestras para estimar velocidad (anti-ruido)


@dataclass(frozen=True)
class Umbrales:
    """Umbrales ajustables (entrenamiento guiado). Defaults = constantes de arriba."""
    cadera_suelo: float = CADERA_SUELO
    cadera_levantado: float = CADERA_LEVANTADO
    angulo_torso: float | None = ANGULO_TORSO   # None = criterio de ángulo desactivado
    suelo_sostenido_s: float = SUELO_SOSTENIDO_S
    exigir_descenso: bool = True                # False (modo demo): basta suelo sostenido


def cadera_z(puntos: Sequence[Sequence[float]]) -> float:
    return (puntos[CADERA_I][2] + puntos[CADERA_D][2]) / 2


def angulo_torso(puntos: Sequence[Sequence[float]]) -> float:
    """Ángulo (grados) del eje hombros->caderas respecto a la vertical."""
    h = [(puntos[HOMBRO_I][k] + puntos[HOMBRO_D][k]) / 2 for k in range(3)]
    c = [(puntos[CADERA_I][k] + puntos[CADERA_D][k]) / 2 for k in range(3)]
    d = [h[k] - c[k] for k in range(3)]
    n = math.sqrt(sum(v * v for v in d))
    if n < 1e-6:
        return 0.0
    return math.degrees(math.acos(min(1.0, abs(d[2]) / n)))


class DetectorCaidas:
    def __init__(self, umbrales: Umbrales | None = None) -> None:
        self.umbrales = umbrales or Umbrales()
        self.caida = False
        self._hist: deque[tuple[float, float]] = deque()
        self._t_descenso: float | None = None
        self._t_suelo: float | None = None
        self._t_alto: float | None = None

    def en_suelo(self, puntos: Sequence[Sequence[float]]) -> bool:
        """Cadera baja y (si el criterio está activo) torso horizontal."""
        u = self.umbrales
        return cadera_z(puntos) < u.cadera_suelo and (
            u.angulo_torso is None or angulo_torso(puntos) > u.angulo_torso)

    def _descenso_rapido(self, t: float, z: float) -> bool:
        while self._hist and t - self._hist[0][0] > VENTANA_CAIDA:
            self._hist.popleft()
        if not self._hist:
            return False
        # caída relativa en la ventana de 1 s
        zmax = max(h[1] for h in self._hist)
        if zmax > 0 and (zmax - z) / zmax > CAIDA_RELATIVA:
            return True
        # velocidad vertical en el último tramo
        for tp, zp in self._hist:
            dt = t - tp
            if dt <= VENTANA_VEL and dt >= MIN_DT_VEL:
                return (z - zp) / dt < VEL_DESCENSO
        return False

    def actualizar(self, t: float, puntos: Sequence[Sequence[float]] | None) -> bool | None:
        """Devuelve el nuevo estado si cambió, si no None. None (oclusión) no cambia nada."""
        if puntos is None:
            return None
        u = self.umbrales
        z = cadera_z(puntos)
        if not self.caida and self._descenso_rapido(t, z):
            self._t_descenso = t
        self._hist.append((t, z))

        if not self.caida:
            armado = not u.exigir_descenso or (
                self._t_descenso is not None and t - self._t_descenso <= ARMADO_S)
            if self.en_suelo(puntos) and (armado or self._t_suelo is not None):
                if self._t_suelo is None:
                    self._t_suelo = t
                if t - self._t_suelo >= u.suelo_sostenido_s:
                    self.caida = True
                    self._t_suelo = self._t_alto = None
                    return True
            else:
                self._t_suelo = None
            return None

        if z > u.cadera_levantado:
            if self._t_alto is None:
                self._t_alto = t
            if t - self._t_alto >= LEVANTADO_SOSTENIDO_S:
                self.caida = False
                self._t_alto = self._t_descenso = None
                self._hist.clear()
                return False
        else:
            self._t_alto = None
        return None
