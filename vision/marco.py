"""Transformación cámara -> habitación.

Marco cámara (RealSense/pinhole): x derecha, y abajo, z hacia delante.
Marco habitación: origen en el suelo bajo la cámara, x derecha, y hacia
delante (lejos de la cámara), z arriba.

La cámara está a `altura` m del suelo, inclinada `pitch` rad hacia abajo.
"""
from __future__ import annotations

import math

import numpy as np

ALTURA_CAMARA = 1.8
PITCH = math.radians(15.0)
OFFSET_TOBILLO = 0.08      # m: el tobillo está ~8 cm sobre el suelo
FOV_VERTICAL_WEBCAM = math.radians(50.0)   # supuesto (webcams típicas 45-60 deg)
ESPAN_NARIZ_TOBILLO = 1.55  # m: distancia nariz -> tobillos de una persona de ~1,70 m
NARIZ, TOBILLO_I, TOBILLO_D = 0, 27, 28


class MarcoHabitacion:
    def __init__(self, altura: float = ALTURA_CAMARA, pitch: float = PITCH) -> None:
        self.altura = altura
        self.pitch = pitch

    def a_habitacion(self, p_cam) -> np.ndarray:
        """(N,3) o (3,) en marco cámara -> mismo shape en marco habitación."""
        p = np.asarray(p_cam, dtype=float)
        xc, yc, zc = p[..., 0], p[..., 1], p[..., 2]
        s, c = math.sin(self.pitch), math.cos(self.pitch)
        return np.stack([xc, zc * c - yc * s, self.altura - zc * s - yc * c], axis=-1)

    def autocalibrar(self, tobillos_cam, offset: float = OFFSET_TOBILLO) -> None:
        """Ajusta altura (y pitch si hay >=3 puntos no alineados) con los
        tobillos (marco cámara) de una persona de PIE: el suelo es z=0.

        Con 1-2 puntos solo se recalcula la altura, conservando el pitch.
        Con >=3 se ajusta un plano al suelo por mínimos cuadrados (SVD).
        """
        pts = np.asarray(tobillos_cam, dtype=float).reshape(-1, 3)
        if len(pts) == 0:
            raise ValueError("sin puntos de calibración")
        if len(pts) >= 3:
            cen = pts.mean(axis=0)
            _, sv, vt = np.linalg.svd(pts - cen)
            if sv[1] > 1e-3:  # no colineales
                n = vt[2]
                if n[1] > 0:       # normal apuntando arriba (yc negativo)
                    n = -n
                pitch = math.atan2(-n[2], -n[1])
                if abs(pitch) < math.radians(80):
                    self.pitch = pitch
                    self.altura = float(-n @ cen) + offset
                    return
        s, c = math.sin(self.pitch), math.cos(self.pitch)
        # altura = z_suelo_tobillo + zc*s + yc*c  (z_suelo_tobillo = offset)
        self.altura = float(np.mean(offset + pts[:, 2] * s + pts[:, 1] * c))


def webcam_a_camara(lm_norm, aspecto: float = 4 / 3,
                    fov_v: float = FOV_VERTICAL_WEBCAM) -> np.ndarray:
    """Landmarks 2D normalizados (u,v en 0..1) -> puntos 3D marco cámara.

    APROXIMACIÓN: una webcam no mide profundidad. Se estima UNA profundidad
    para toda la persona a partir del tamaño en imagen de la distancia
    nariz->tobillos (ESPAN_NARIZ_TOBILLO m reales) con modelo pinhole y FOV
    vertical supuesto. Error típico +-20-30 % en distancia; la altura
    relativa (cadera) es razonable si el pitch y la altura de cámara están
    bien. No usar para medidas clínicas. Sin tobillos visibles la
    estimación falla (se usa el último dato válido, ver FuentePose).
    """
    lm = np.asarray(lm_norm, dtype=float)[:, :2]
    f = 0.5 / math.tan(fov_v / 2)          # focal en unidades de alto de imagen
    ux = (lm[:, 0] - 0.5) * aspecto
    vy = lm[:, 1] - 0.5
    tob = (lm[TOBILLO_I] + lm[TOBILLO_D]) / 2
    dx, dy = (lm[NARIZ, 0] - tob[0]) * aspecto, lm[NARIZ, 1] - tob[1]
    espan = math.hypot(dx, dy)
    if espan < 1e-3:
        raise ValueError("persona demasiado pequeña para estimar profundidad")
    zc = ESPAN_NARIZ_TOBILLO * f / espan
    return np.stack([ux * zc / f, vy * zc / f, np.full(len(lm), zc)], axis=1)
