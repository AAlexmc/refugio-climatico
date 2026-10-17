import asyncio
import time

import numpy as np

import vision.pose as m
from vision.pose import Cuadro, FuentePose, profundidad_mediana
from nucleo.bus import Bus


def test_mediana_5x5_descarta_ceros():
    d = np.zeros((20, 20), dtype=np.uint16)
    d[8:13, 8:13] = 2000
    d[10, 10] = 0
    d[9, 9] = 5000   # outlier
    assert profundidad_mediana(d, 10, 10) == 2.0
    assert profundidad_mediana(np.zeros((20, 20), dtype=np.uint16), 10, 10) is None


class CapturaFalsa:
    def leer(self):
        time.sleep(0.005)
        return Cuadro(np.zeros((480, 640, 3), np.uint8))


async def test_captura_inyectada_publica_pose_sin_rgb():
    bus = Bus()
    lm = np.full((33, 3), 0.5)
    lm[0] = [0.5, 0.2, 0]
    lm[27] = lm[28] = [0.5, 0.8, 0]
    f = FuentePose("webcam", fps=100, captura=CapturaFalsa(),
                   estimador=lambda c: (lm, np.ones(33)))
    eventos = []
    bus.oyente(eventos.append)
    t = asyncio.create_task(f.correr(bus))
    await asyncio.sleep(0.4)
    t.cancel()
    f._parar.set()
    poses = [e for e in eventos if e.tipo == "pose"]
    assert poses and all(len(e.valor["puntos"]) == 33 for e in poses)
    assert poses[0].valor["visible"] is True
    assert set(poses[0].valor) == {"puntos", "cadera_z", "visible"}
    assert any(e.tipo == "estado_fuente" and e.valor["conectada"] for e in eventos)


async def test_sin_camara_publica_desconectada_y_reintenta(monkeypatch):
    monkeypatch.setattr(m, "REINTENTO_S", 0.05)

    def falla(*a, **k):
        raise RuntimeError("sin dispositivo")
    monkeypatch.setattr(m, "CapturaRealSense", falla)
    bus = Bus()
    eventos = []
    bus.oyente(eventos.append)
    f = FuentePose("realsense")
    t = asyncio.create_task(f.correr(bus))
    await asyncio.sleep(0.3)
    t.cancel()
    f._parar.set()
    est = [e for e in eventos if e.tipo == "estado_fuente"]
    assert len(est) >= 2 and not est[0].valor["conectada"]
