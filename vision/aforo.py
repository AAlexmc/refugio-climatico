"""Conteo de personas con la RealSense D435i + etiquetas (Ordenador 1).

La MISMA RealSense que hace pose/caídas cuenta personas: `FuentePose` llama a
`ContadorYolo` sobre el mismo cuadro (un solo `rs.pipeline`). Detector YOLO
(clase person) + tracker ByteTrack de ultralytics -> etiqueta estable
"Persona 3"; la profundidad da su posición (x, y) en metros, marco refugio
(z arriba), para los avatares del gemelo 3D.

Eventos: `aforo` (int, suavizado) y `personas`
([{"id", "x", "y", "etiqueta", "estado"}]; x/y None sin profundidad).

Privacidad (línea roja): NUNCA se guardan fotos ni vídeo. La imagen vive
solo en memoria del frame actual; sale el número, etiquetas y posiciones.
Con --ver-camara, /camara.mjpg muestra cajas + etiquetas con la cabeza
difuminada, sin escribir a disco.

`FuenteAforo` (registro "yolo") es para contar con una cámara SIN pose
(webcam o una segunda RealSense). Con `--pose realsense` no hace falta.
"""
from __future__ import annotations

import asyncio
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nucleo.bus import Bus
from nucleo.evento import Evento

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "modelos" / "yolo26n.pt"
CONF_MIN = 0.40
PROF_MAX_M = 6.0           # más lejos = fuera del refugio (calle), no cuenta
VENTANA_SUAVIZADO = 5      # frames: mediana para que el aforo no parpadee
REPUBLICAR_S = 5.0


@dataclass(frozen=True)
class Deteccion:
    id: int | None                          # id del tracker (None mientras arranca)
    caja: tuple[float, float, float, float]  # x1, y1, x2, y2 en píxeles
    conf: float


class ContadorYolo:
    """`f(cuadro) -> list[Deteccion]`. Carga perezosa del modelo (GPU si hay)."""

    def __init__(self, modelo: str | Path = MODELO, conf: float = CONF_MIN) -> None:
        from ultralytics import YOLO
        ruta = Path(modelo)
        if not ruta.exists():
            raise RuntimeError(f"falta el modelo {ruta} (cópialo a modelos/, ver modelos/LEEME.md)")
        self._yolo = YOLO(str(ruta))
        self.conf = conf

    def __call__(self, cuadro) -> list[Deteccion]:
        r = self._yolo.track(cuadro.bgr, persist=True, classes=[0], conf=self.conf,
                             tracker="bytetrack.yaml", verbose=False)[0]
        b = r.boxes
        if b is None or len(b) == 0:
            return []
        ids = b.id.int().tolist() if b.id is not None else [None] * len(b)
        return [Deteccion(i, tuple(map(float, xyxy)), float(c))
                for i, xyxy, c in zip(ids, b.xyxy.tolist(), b.conf.tolist())]


def estado_caja(caja) -> str:
    """Postura aproximada por la forma de la caja (ancha y baja = en el suelo)."""
    x1, y1, x2, y2 = caja
    w, h = max(x2 - x1, 1.0), max(y2 - y1, 1.0)
    r = w / h
    return "suelo" if r > 1.3 else ("sentado" if r > 0.75 else "de_pie")


def posicion(caja, cuadro, marco) -> tuple[float, float] | None:
    """(x, y) en el suelo del refugio con la mediana de profundidad del torso."""
    if cuadro.profundidad is None or cuadro.intrinsecos is None:
        return None
    x1, y1, x2, y2 = caja
    h, w = cuadro.profundidad.shape
    u0, u1 = int(x1 + 0.35 * (x2 - x1)), int(x1 + 0.65 * (x2 - x1)) + 1
    v0, v1 = int(y1 + 0.25 * (y2 - y1)), int(y1 + 0.55 * (y2 - y1)) + 1
    ven = cuadro.profundidad[max(0, v0):min(h, v1), max(0, u0):min(w, u1)]
    val = ven[ven > 0]
    if val.size == 0:
        return None
    z = float(np.median(val)) / 1000.0
    fx, fy, cx, cy = cuadro.intrinsecos
    u, v = (x1 + x2) / 2, (v0 + v1) / 2
    p = marco.a_habitacion(np.array([(u - cx) * z / fx, (v - cy) * z / fy, z]))
    return float(p[0]), float(p[1])


def personas(dets: list[Deteccion], cuadro, marco, prof_max: float = PROF_MAX_M) -> list[dict]:
    out = []
    for d in dets:
        pos = posicion(d.caja, cuadro, marco)
        if pos is not None and pos[1] > prof_max:
            continue
        out.append({"id": d.id, "x": None if pos is None else round(pos[0], 2),
                    "y": None if pos is None else round(pos[1], 2),
                    "etiqueta": f"Persona {d.id}" if d.id is not None else "Persona ?",
                    "estado": estado_caja(d.caja)})
    return out


class Aforo:
    """Suaviza el conteo y decide cuándo publicar (cambio o cada REPUBLICAR_S)."""

    def __init__(self, ventana: int = VENTANA_SUAVIZADO, republicar_s: float = REPUBLICAR_S) -> None:
        self._n: deque[int] = deque(maxlen=ventana)
        self.republicar_s = republicar_s
        self.valor: int | None = None
        self._t_pub = -1e9

    def actualizar(self, t: float, n: int) -> int | None:
        self._n.append(n)
        v = int(statistics.median_low(self._n))
        if v != self.valor or t - self._t_pub >= self.republicar_s:
            self.valor, self._t_pub = v, t
            return v
        return None


def dibujar_cajas(img: np.ndarray, dets: list[Deteccion], gente: list[dict]) -> np.ndarray:
    """Cajas + etiqueta; cabeza difuminada (privacidad visible en la demo). Modifica `img`."""
    import cv2
    for d, p in zip(dets, gente):
        x1, y1, x2, y2 = (int(v) for v in d.caja)
        hy = y1 + max(1, (y2 - y1) // 5)
        roi = img[max(0, y1):hy, max(0, x1):x2]
        if roi.size:
            img[max(0, y1):hy, max(0, x1):x2] = cv2.GaussianBlur(roi, (31, 31), 0)
        col = (60, 60, 255) if p["estado"] == "suelo" else (255, 200, 60)
        cv2.rectangle(img, (x1, y1), (x2, y2), col, 2)
        cv2.putText(img, f'{p["etiqueta"]} · {p["estado"]}', (x1 + 3, max(14, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2, cv2.LINE_AA)
    cv2.putText(img, f"AFORO {len(gente)}", (8, img.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (255, 255, 255), 2, cv2.LINE_AA)
    return img


class FuenteAforo:
    """Solo conteo (sin pose), con su propia cámara."""

    def __init__(self, camara: str = "realsense", modelo: str | Path = MODELO, fps: int = 5,
                 refugio: str = "R1", captura=None, contador=None, ver: bool = False) -> None:
        self.camara, self.modelo, self.fps, self.refugio = camara, modelo, fps, refugio
        self._captura, self._contador, self.ver = captura, contador, ver
        self._aforo = Aforo()
        self._parar = threading.Event()

    async def correr(self, bus: Bus) -> None:
        bus.enlazar_loop(asyncio.get_running_loop())
        tarea = asyncio.ensure_future(asyncio.to_thread(self._bucle, bus))
        try:
            await asyncio.shield(tarea)
        except asyncio.CancelledError:
            self._parar.set()
            raise

    def _pub(self, bus: Bus, tipo: str, valor) -> None:
        bus.publicar_desde_hilo(Evento(tipo, valor, "yolo", self.refugio))

    def _bucle(self, bus: Bus) -> None:
        from vision.marco import MarcoHabitacion
        from vision.pose import CapturaRealSense, CapturaWebcam
        marco = MarcoHabitacion()
        while not self._parar.is_set():
            cap = None
            try:
                cap = self._captura or (CapturaRealSense() if self.camara == "realsense" else CapturaWebcam())
                cont = self._contador or ContadorYolo(self.modelo)
            except Exception as e:
                self._pub(bus, "estado_fuente", {"conectada": False, "detalle": f"aforo: {e}"})
                if cap is not None and self._captura is None:
                    cap.cerrar()
                self._parar.wait(2.0)
                continue
            self._pub(bus, "estado_fuente", {"conectada": True, "detalle": f"aforo {self.camara}"})
            try:
                while not self._parar.is_set():
                    cuadro = cap.leer()
                    if cuadro is None:
                        raise RuntimeError("sin frames")
                    self.procesar(bus, cuadro, cont, marco)
                    self._parar.wait(1.0 / self.fps)
            except Exception as e:
                self._pub(bus, "estado_fuente", {"conectada": False, "detalle": f"aforo: {e}"})
            finally:
                if self._captura is None:
                    cap.cerrar()
            if self._captura is not None:
                return

    def procesar(self, bus: Bus, cuadro, cont, marco) -> None:
        dets = cont(cuadro)
        gente = personas(dets, cuadro, marco)
        if self.ver:
            from vision.vista import VISTA, jpeg
            VISTA.publicar(jpeg(dibujar_cajas(cuadro.bgr.copy(), dets, gente)))
        self._pub(bus, "personas", gente)
        n = self._aforo.actualizar(time.monotonic(), len(gente))
        if n is not None:
            self._pub(bus, "aforo", n)
