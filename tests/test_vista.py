import numpy as np
from fastapi.testclient import TestClient

from servidor.app import crear_app
from vision.vista import VISTA, Vista, dibujar


def test_dibujar_devuelve_jpeg_con_y_sin_persona():
    bgr = np.zeros((480, 640, 3), np.uint8)
    lm = np.full((33, 3), 0.5)
    vis = np.ones(33)
    pts = [[0.0, 0.0, 1.0]] * 33
    for r, p in (((lm, vis), pts), (None, None)):
        jpg = dibujar(bgr, r, p, 0.5, np.zeros((480, 640), np.uint16))
        assert jpg[:2] == b"\xff\xd8" and jpg[-2:] == b"\xff\xd9"


def test_vista_esperar_entrega_el_cuadro_nuevo():
    v = Vista()
    v.publicar(b"a")
    n, jpg = v.esperar(0, timeout=0.1)
    assert (n, jpg) == (1, b"a")


def test_camara_404_sin_ver_camara():
    VISTA.activa = False
    with TestClient(crear_app([])) as c:
        assert c.get("/camara.mjpg").status_code == 404
        assert c.get("/camara.html").status_code == 200
