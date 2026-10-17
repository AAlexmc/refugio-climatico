"""Entrenamiento de la detección de caídas: grabar de pie / en el suelo,
calcular umbrales y persistirlos (JSON, escritura atómica).

Lógica pura, sin cámara. Los umbrales aprendidos absorben el error del
`MarcoHabitacion` (cámara a 1 m, casi horizontal): se miden en la misma
colocación en que se va a usar.
"""
from __future__ import annotations

import json
import logging
import os
import statistics
import threading
from dataclasses import asdict
from pathlib import Path

from vision.caidas import Umbrales, angulo_torso, cadera_z

log = logging.getLogger(__name__)

RUTA = Path(__file__).resolve().parent.parent / "datos" / "caida_calibracion.json"
HUECO_MIN_M = 0.15            # menos que esto: no se distingue de pie de suelo
FRAC_SUELO, FRAC_LEVANTADO = 0.35, 0.65   # posición de los umbrales en el hueco
MUESTRAS_MIN = 5
ANGULO_SUELO_MIN = 50.0       # por debajo, el torso en el suelo no es horizontal (¿sentado?)
ANGULO_MIN, ANGULO_MAX = 60.0, 75.0   # rango del umbral de torso horizontal
FRAC_ANGULO = 0.75            # posición del umbral entre el ángulo de pie y el del suelo


class ErrorCalibracion(ValueError):
    pass


def validar(d: dict) -> Umbrales:
    """dict (JSON) -> Umbrales; ValueError/ErrorCalibracion si es incoherente."""
    try:
        suelo = float(d["cadera_suelo"])
        alto = float(d["cadera_levantado"])
        ang = d.get("angulo_torso")
        ang = None if ang is None else float(ang)
        sost = float(d.get("suelo_sostenido_s", Umbrales.suelo_sostenido_s))
        exigir = d.get("exigir_descenso", True)
    except (KeyError, TypeError, ValueError) as e:
        raise ErrorCalibracion(f"umbrales mal formados: {e}")
    if not isinstance(exigir, bool):
        raise ErrorCalibracion("exigir_descenso debe ser true o false")
    if not (-3.0 < suelo < alto < 3.0):
        raise ErrorCalibracion("se exige -3 < cadera_suelo < cadera_levantado < 3 m "
                               "(alturas relativas al marco de la habitación)")
    if ang is not None and not (5.0 <= ang <= 89.0):
        raise ErrorCalibracion("angulo_torso debe estar entre 5 y 89 grados (o null)")
    if not (0.2 <= sost <= 10.0):
        raise ErrorCalibracion("suelo_sostenido_s debe estar entre 0,2 y 10 s")
    return Umbrales(suelo, alto, ang, sost, exigir)


def mediana(muestras: list[tuple[float, float]]) -> dict:
    """[(cadera_z, angulo)] -> {muestras, cadera_z, angulo} (medianas)."""
    if len(muestras) < MUESTRAS_MIN:
        raise ErrorCalibracion(
            f"solo {len(muestras)} muestras: no veo a la persona (¿se ven hombros y caderas?)")
    return {"muestras": len(muestras),
            "cadera_z": statistics.median(m[0] for m in muestras),
            "angulo": statistics.median(m[1] for m in muestras)}


def calcular(pie: dict, suelo: dict, *, exigir_descenso: bool = True) -> tuple[Umbrales, str]:
    """Medianas {cadera_z, angulo} de pie y en el suelo -> (umbrales, nota para la UI)."""
    try:
        zp, ap = float(pie["cadera_z"]), float(pie["angulo"])
        zs, a_s = float(suelo["cadera_z"]), float(suelo["angulo"])
    except (KeyError, TypeError, ValueError) as e:
        raise ErrorCalibracion(f"faltan medianas de pie/suelo: {e}")
    hueco = zp - zs
    if hueco < HUECO_MIN_M:
        raise ErrorCalibracion(
            f"Hueco de cadera {hueco:.2f} m (< {HUECO_MIN_M} m): no distingo de pie y suelo, "
            "recoloca la cámara.")
    if a_s < ANGULO_SUELO_MIN:
        raise ErrorCalibracion(
            f"Torso en el suelo a {a_s:.0f}° (< {ANGULO_SUELO_MIN:.0f}°): túmbate en el suelo, "
            "no te sientes: necesito el torso horizontal.")
    cs = zs + FRAC_SUELO * hueco
    cl = zs + FRAC_LEVANTADO * hueco
    ang = min(max(ap + FRAC_ANGULO * (a_s - ap), ANGULO_MIN), ANGULO_MAX)
    nota = (f"Cadera: suelo < {cs:.2f} m, levantado > {cl:.2f} m "
            f"(de pie {zp:.2f} m, suelo {zs:.2f} m). "
            f"Torso horizontal si > {ang:.0f}° (de pie {ap:.0f}°, suelo {a_s:.0f}°).")
    return Umbrales(round(cs, 3), round(cl, 3), round(ang, 1),
                    exigir_descenso=exigir_descenso), nota


def guardar(u: Umbrales, ruta: Path = RUTA) -> None:
    """Escritura atómica: tmp + rename."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(json.dumps(asdict(u), indent=2))
    os.replace(tmp, ruta)


def cargar(ruta: Path = RUTA) -> Umbrales | None:
    """None si no hay fichero o está roto (se usan los defaults; nunca tumba el arranque)."""
    try:
        return validar(json.loads(Path(ruta).read_text()))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:   # JSON roto o incoherente
        log.warning("calibración de caídas ignorada (%s): %s", ruta, e)
        return None


def borrar(ruta: Path = RUTA) -> None:
    Path(ruta).unlink(missing_ok=True)


class Grabador:
    """Acumula (cadera_z, ángulo) de las poses visibles mientras está activo."""

    def __init__(self) -> None:
        self.activo = False
        self._m: list[tuple[float, float]] = []
        self._lock = threading.Lock()

    def empezar(self) -> None:
        with self._lock:
            self._m = []
            self.activo = True

    def anadir(self, puntos) -> None:
        if self.activo:
            m = (float(cadera_z(puntos)), float(angulo_torso(puntos)))
            with self._lock:
                self._m.append(m)

    def terminar(self) -> list[tuple[float, float]]:
        with self._lock:
            self.activo = False
            return list(self._m)
