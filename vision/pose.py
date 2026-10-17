"""Fuente de pose: cámara -> MediaPipe -> marco habitación -> pose / caida.

El frame RGB vive solo dentro del hilo de captura: nunca se publica ni se
guarda. Por el bus solo salen 33 puntos en metros.

`captura` inyectable (tests): objeto con `leer() -> Cuadro | None` y
`cerrar()`. `estimador` inyectable: `f(cuadro) -> (landmarks_norm, visibilidad)`
o None si no hay persona; con `cerrar()` opcional.
"""
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass

import numpy as np

from vision import calibracion
from vision.caidas import (CADERA_D, CADERA_I, HOMBRO_D, HOMBRO_I, DetectorCaidas, Umbrales,
                            angulo_torso, cadera_z)
from vision.desmayo import DetectorDesmayo, cadera_xy
from vision.marco import MarcoHabitacion, webcam_a_camara
from nucleo.bus import Bus
from nucleo.evento import Evento

REINTENTO_S = 2.0
VISIBILIDAD_MIN = 0.5           # de hombros y caderas para considerar "visible"
VENTANA_PROF = 2                # radio: ventana 5x5
PROF_MIN_M, PROF_MAX_M = 0.3, 8.0
_CLAVE = (HOMBRO_I, HOMBRO_D, CADERA_I, CADERA_D)


@dataclass
class Cuadro:
    bgr: np.ndarray                        # (H,W,3) uint8
    profundidad: np.ndarray | None = None  # (H,W) uint16 mm alineada a color (RealSense)
    intrinsecos: tuple[float, float, float, float] | None = None  # fx, fy, cx, cy


class CapturaRealSense:
    """D435i RGB + profundidad alineada (basado en perception/realsense_capture.py)."""

    def __init__(self, ancho: int = 640, alto: int = 480, fps: int = 30) -> None:
        import pyrealsense2 as rs
        self._pipe = rs.pipeline()
        cfg = rs.config()
        cfg.enable_stream(rs.stream.color, ancho, alto, rs.format.bgr8, fps)
        cfg.enable_stream(rs.stream.depth, ancho, alto, rs.format.z16, fps)
        perfil = self._pipe.start(cfg)
        self._align = rs.align(rs.stream.color)
        i = perfil.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
        self._intr = (i.fx, i.fy, i.ppx, i.ppy)

    def leer(self) -> Cuadro | None:
        frames = self._pipe.wait_for_frames()
        while True:  # descarta frames viejos acumulados
            nuevo = self._pipe.poll_for_frames()
            if not nuevo:
                break
            frames = nuevo
        al = self._align.process(frames)
        c, d = al.get_color_frame(), al.get_depth_frame()
        if not c or not d:
            return None
        return Cuadro(np.asanyarray(c.get_data()), np.asanyarray(d.get_data()), self._intr)

    def cerrar(self) -> None:
        self._pipe.stop()


class CapturaWebcam:
    def __init__(self, indice: int = 0) -> None:
        import cv2
        self._cap = cv2.VideoCapture(indice)
        if not self._cap.isOpened():
            raise RuntimeError(f"webcam {indice} no disponible")

    def leer(self) -> Cuadro | None:
        ok, bgr = self._cap.read()
        return Cuadro(bgr) if ok else None

    def cerrar(self) -> None:
        self._cap.release()


class EstimadorMediaPipe:
    def __init__(self) -> None:
        import mediapipe as mp
        self._pose = mp.solutions.pose.Pose(model_complexity=0, min_detection_confidence=0.5,
                                            min_tracking_confidence=0.5)

    def __call__(self, cuadro: Cuadro):
        import cv2
        res = self._pose.process(cv2.cvtColor(cuadro.bgr, cv2.COLOR_BGR2RGB))
        if not res.pose_landmarks:
            return None
        lm = res.pose_landmarks.landmark
        return (np.array([[p.x, p.y, p.z] for p in lm]), np.array([p.visibility for p in lm]))

    def cerrar(self) -> None:
        self._pose.close()


def profundidad_mediana(prof_mm: np.ndarray, u: float, v: float) -> float | None:
    """Mediana (m) en ventana 5x5 alrededor del píxel, descartando ceros."""
    h, w = prof_mm.shape
    cu, cv_ = int(round(u)), int(round(v))
    if not (0 <= cu < w and 0 <= cv_ < h):
        return None
    ven = prof_mm[max(0, cv_ - VENTANA_PROF):cv_ + VENTANA_PROF + 1,
                  max(0, cu - VENTANA_PROF):cu + VENTANA_PROF + 1]
    val = ven[ven > 0]
    if val.size == 0:
        return None
    m = float(np.median(val)) / 1000.0
    return m if PROF_MIN_M <= m <= PROF_MAX_M else None


def a_camara_realsense(lm_norm: np.ndarray, cuadro: Cuadro) -> np.ndarray | None:
    """Landmarks normalizados + profundidad -> puntos 3D marco cámara (deproyección)."""
    h, w = cuadro.profundidad.shape
    fx, fy, cx, cy = cuadro.intrinsecos
    zs = [profundidad_mediana(cuadro.profundidad, p[0] * w, p[1] * h) for p in lm_norm]
    validas = [z for z in zs if z is not None]
    if not validas:
        return None
    mediana = float(np.median(validas))
    zs = np.array([mediana if z is None else z for z in zs])  # huecos: profundidad del cuerpo
    u, v = lm_norm[:, 0] * w, lm_norm[:, 1] * h
    return np.stack([(u - cx) * zs / fx, (v - cy) * zs / fy, zs], axis=1)


def persona_cercana(gente: list[dict], xy, radio: float = 1.0) -> int | None:
    """Id de la persona etiquetada más cercana a la cadera del esqueleto."""
    if xy is None:
        return None
    mejor, dmin = None, radio
    for p in gente:
        if p.get("x") is None or p.get("id") is None:
            continue
        d = ((p["x"] - xy[0]) ** 2 + (p["y"] - xy[1]) ** 2) ** 0.5
        if d < dmin:
            mejor, dmin = p["id"], d
    return mejor


class FuentePose:
    def __init__(self, camara: str = "realsense", *, fps: int = 10, captura=None,
                 estimador=None, marco: MarcoHabitacion | None = None, reloj=time.monotonic,
                 refugio: str = "R1", ver: bool = False,
                 calibracion_ruta=None, contar: bool = False, contador=None,
                 desmayo: DetectorDesmayo | None = None) -> None:
        if camara not in ("realsense", "webcam"):
            raise ValueError(f"camara desconocida: {camara!r}")
        self.camara = camara
        self.fps = fps
        self.refugio = refugio
        self.ver = ver                 # --ver-camara: publica JPEG con esqueleto en local
        self._r = None
        self.marco = marco or MarcoHabitacion()
        self._captura = captura
        self._estimador = estimador
        self._reloj = reloj
        self._parar = threading.Event()
        self.calibracion_ruta = calibracion_ruta or calibracion.RUTA
        self._detector = DetectorCaidas(calibracion.cargar(self.calibracion_ruta))
        self._grabador = calibracion.Grabador()
        self.vivo: dict = {"visible": False, "estado": "sin_persona", "cadera_z": None,
                           "angulo": None, "t": None}
        self._ultimos: list[list[float]] = [[0.0, 0.0, 0.0]] * 33
        # aforo con la misma cámara (vision/aforo.py); contador inyectable en tests
        self.contar = contar or contador is not None
        self._contador = contador
        self._aforo = None
        self._gente: list[dict] = []
        self._desmayo = desmayo or DetectorDesmayo()

    @property
    def umbrales(self) -> Umbrales:
        return self._detector.umbrales

    @property
    def caida(self) -> bool:
        return self._detector.caida

    def aplicar_umbrales(self, u: Umbrales) -> None:
        """En caliente: el detector lee los umbrales en cada frame."""
        self._detector.umbrales = u

    async def grabar(self, segundos: float) -> list[tuple[float, float]]:
        """Recoge (cadera_z, ángulo) de las poses visibles durante `segundos`."""
        if self._grabador.activo:
            raise RuntimeError("ya se está grabando")
        self._grabador.empezar()
        try:
            await asyncio.sleep(segundos)
        finally:
            muestras = self._grabador.terminar()
        return muestras

    async def correr(self, bus: Bus) -> None:
        bus.enlazar_loop(asyncio.get_running_loop())
        tarea = asyncio.ensure_future(asyncio.to_thread(self._bucle, bus))
        try:
            await asyncio.shield(tarea)
        except asyncio.CancelledError:
            self._parar.set()
            raise

    def _pub(self, bus: Bus, tipo: str, valor) -> None:
        bus.publicar_desde_hilo(Evento(tipo, valor, self.camara, self.refugio))

    def _estado(self, bus: Bus, conectada: bool, detalle: str) -> None:
        self._pub(bus, "estado_fuente", {"conectada": conectada, "detalle": detalle})

    def _bucle(self, bus: Bus) -> None:
        inyectada = self._captura is not None
        while not self._parar.is_set():
            cap = est = None
            try:
                cap = self._captura if inyectada else (
                    CapturaRealSense() if self.camara == "realsense" else CapturaWebcam())
                est = self._estimador or EstimadorMediaPipe()
            except Exception as e:  # sin cámara / sin librería: reintentar
                self._estado(bus, False, f"{self.camara}: {e}")
                self._cerrar(cap if not inyectada else None)
                self._parar.wait(REINTENTO_S)
                continue
            self._estado(bus, True, self.camara)
            cont = self._abrir_contador(bus) if self.contar else None
            try:
                self._servir(bus, cap, est, cont)
            except Exception as e:
                self._estado(bus, False, f"{self.camara}: {e}")
            finally:
                if not inyectada:
                    self._cerrar(cap)
                if self._estimador is None:
                    self._cerrar(est)
                if self._contador is None:
                    self._aforo = None
            if inyectada:  # una captura inyectada no se puede reabrir
                return
            self._parar.wait(REINTENTO_S)

    def _abrir_contador(self, bus: Bus):
        """YOLO para el aforo; si falla, la pose sigue sola (y se avisa)."""
        from vision.aforo import Aforo, ContadorYolo
        self._aforo = Aforo()
        if self._contador is not None:
            return self._contador
        try:
            return ContadorYolo()
        except Exception as e:
            self._estado(bus, False, f"aforo: {e}")
            return None

    def _contar(self, bus: Bus, cuadro: Cuadro, cont):
        from vision.aforo import personas
        dets = cont(cuadro)
        self._gente = personas(dets, cuadro, self.marco)
        self._pub(bus, "personas", self._gente)
        n = self._aforo.actualizar(self._reloj(), len(self._gente))
        if n is not None:
            self._pub(bus, "aforo", n)
        return dets

    @staticmethod
    def _cerrar(obj) -> None:
        try:
            if obj is not None and hasattr(obj, "cerrar"):
                obj.cerrar()
        except Exception:
            pass

    def _servir(self, bus: Bus, cap, est, cont=None) -> None:
        paso = 1.0 / self.fps
        siguiente = self._reloj()
        while not self._parar.is_set():
            cuadro = cap.leer()
            if cuadro is None:
                raise RuntimeError("sin frames")
            puntos = self._procesar(cuadro, est)
            dets = self._contar(bus, cuadro, cont) if cont is not None else None
            if self.ver:
                from vision.vista import VISTA, dibujar
                VISTA.publicar(dibujar(cuadro.bgr, self._r, puntos, VISIBILIDAD_MIN,
                                       cuadro.profundidad,
                                       None if dets is None else (dets, self._gente)))
            del cuadro  # el RGB no sale de aquí
            self._publicar(bus, self._reloj(), puntos)
            siguiente += paso
            resto = siguiente - self._reloj()
            if resto > 0:
                self._parar.wait(resto)
            else:
                siguiente = self._reloj()

    def _procesar(self, cuadro: Cuadro, est) -> list[list[float]] | None:
        r = self._r = est(cuadro)
        if r is None:
            return None
        lm, vis = r
        if min(vis[i] for i in _CLAVE) < VISIBILIDAD_MIN:
            return None
        try:
            if cuadro.profundidad is not None and cuadro.intrinsecos is not None:
                cam = a_camara_realsense(lm, cuadro)
            else:
                h, w = cuadro.bgr.shape[:2]
                cam = webcam_a_camara(lm, aspecto=w / h)
        except ValueError:
            return None
        if cam is None:
            return None
        return self.marco.a_habitacion(cam).tolist()

    def _publicar(self, bus: Bus, t: float, puntos: list[list[float]] | None) -> None:
        if puntos is not None:
            self._ultimos = puntos
            self._grabador.anadir(puntos)
            if self._detector.caida:
                estado = "caida"
            else:
                estado = "suelo" if self._detector.en_suelo(puntos) else "de_pie"
            self.vivo = {"visible": True, "estado": estado, "cadera_z": float(cadera_z(puntos)),
                         "angulo": float(angulo_torso(puntos)), "t": time.time()}
        else:
            self.vivo = {**self.vivo, "visible": False, "t": time.time(),
                         "estado": "caida" if self._detector.caida else "sin_persona"}
        self._pub(bus, "pose", {"puntos": self._ultimos,
                                "cadera_z": float(cadera_z(self._ultimos)),
                                "visible": puntos is not None})
        cambio = self._detector.actualizar(t, puntos)
        if cambio is not None:
            self._pub(bus, "caida", cambio)
        xy = cadera_xy(puntos) if puntos is not None else None
        d = self._desmayo.actualizar(t, self._detector.caida, xy, persona_cercana(self._gente, xy))
        if d is not None:
            self._pub(bus, "desmayo", d)
