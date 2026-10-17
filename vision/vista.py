"""Vista de depuración de la cámara (solo con `--ver-camara`).

Por defecto el RGB nunca sale del hilo de captura. Con `--ver-camara` el
servidor publica en local (`/camara.mjpg`) el último cuadro con el esqueleto
MediaPipe dibujado, para ajustar la cámara. No se guarda nada en disco.
"""
from __future__ import annotations

import threading
import time

import numpy as np

# pares de landmarks MediaPipe Pose que se dibujan como huesos
HUESOS = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24),
          (23, 25), (25, 27), (24, 26), (26, 28), (27, 31), (28, 32), (0, 11), (0, 12)]
_CLAVE = (11, 12, 23, 24)


class Vista:
    """Último JPEG compartido entre el hilo de la cámara y el servidor."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._jpeg: bytes | None = None
        self._n = 0
        self.activa = False

    def publicar(self, jpeg: bytes) -> None:
        with self._cond:
            self._jpeg = jpeg
            self._n += 1
            self._cond.notify_all()

    def esperar(self, visto: int, timeout: float = 1.0) -> tuple[int, bytes | None]:
        """Bloquea hasta que haya un cuadro más nuevo que `visto` (o timeout)."""
        with self._cond:
            self._cond.wait_for(lambda: self._n != visto, timeout)
            return self._n, self._jpeg


VISTA = Vista()


def jpeg(img: np.ndarray) -> bytes:
    import cv2
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return buf.tobytes() if ok else b""


def dibujar(bgr: np.ndarray, r, puntos, vis_min: float, prof: np.ndarray | None = None,
            cajas=None) -> bytes:
    """JPEG del cuadro con esqueleto, estado, miniatura de profundidad y, si hay
    conteo, cajas + etiquetas con la cabeza difuminada (`cajas` = (dets, personas))."""
    import cv2
    img = bgr.copy()
    if cajas is not None:
        from vision.aforo import dibujar_cajas
        dibujar_cajas(img, *cajas)
    h, w = img.shape[:2]
    if r is not None:
        lm, vis = r
        px = [(int(p[0] * w), int(p[1] * h)) for p in lm]
        for a, b in HUESOS:
            ok = vis[a] >= vis_min and vis[b] >= vis_min
            cv2.line(img, px[a], px[b], (80, 230, 120) if ok else (90, 90, 90), 3, cv2.LINE_AA)
        for i, p in enumerate(px):
            col = (0, 200, 255) if i in _CLAVE else (255, 220, 120)
            cv2.circle(img, p, 5 if i in _CLAVE else 3, col if vis[i] >= vis_min else (90, 90, 90), -1)
        faltan = [n for i, n in zip(_CLAVE, ("hombro I", "hombro D", "cadera I", "cadera D"))
                  if vis[i] < vis_min]
    else:
        faltan = ["sin persona"]
    if puntos is not None:
        cz = (puntos[23][2] + puntos[24][2]) / 2
        txt, col = f"POSE OK  cadera z={cz:.2f} m", (80, 230, 120)
    else:
        txt, col = "NO VALE: " + ", ".join(faltan), (60, 60, 255)
    cv2.rectangle(img, (0, 0), (w, 30), (0, 0, 0), -1)
    cv2.putText(img, txt, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2, cv2.LINE_AA)
    cv2.putText(img, time.strftime("%H:%M:%S"), (w - 90, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (200, 200, 200), 1, cv2.LINE_AA)
    if prof is not None:
        mini = cv2.resize(prof, (w // 4, h // 4), interpolation=cv2.INTER_NEAREST)
        mini = cv2.applyColorMap(cv2.convertScaleAbs(mini, alpha=255 / 4000), cv2.COLORMAP_TURBO)
        img[h - mini.shape[0]:, w - mini.shape[1]:] = mini
    return jpeg(img)
