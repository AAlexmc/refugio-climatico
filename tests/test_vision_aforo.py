"""Aforo con etiquetas, desmayo y visión simulada (Ordenador 1)."""
import asyncio
from pathlib import Path

import numpy as np
import pytest

from nucleo.bus import Bus
from nucleo.evento import Evento
from vision.aforo import MODELO, Aforo, Deteccion, estado_caja, personas
from vision.desmayo import DetectorDesmayo
from vision.marco import MarcoHabitacion
from vision.modo_pose import Conmutador
from vision.pose import Cuadro, FuentePose, persona_cercana
from vision.sim_vision import BANCOS, DE_PIE, FuenteVisionSim


# -- desmayo -----------------------------------------------------------------
def test_desmayo_solo_tras_inmovil():
    d = DetectorDesmayo(inmovil_s=5)
    assert d.actualizar(0, True, (1.0, 2.0)) is None
    assert d.actualizar(4.9, True, (1.05, 2.0)) is None
    v = d.actualizar(5.0, True, (1.05, 2.0), persona=3)
    assert v["activo"] is True and v["persona"] == 3 and v["segundos_inmovil"] == 5.0
    assert d.actualizar(6, True, (1.0, 2.0)) is None          # ya activo: sin repetir
    assert d.actualizar(7, False, None)["activo"] is False


def test_desmayo_se_reinicia_si_se_mueve():
    d = DetectorDesmayo(inmovil_s=5)
    d.actualizar(0, True, (0.0, 2.0))
    d.actualizar(4, True, (0.5, 2.0))                         # se arrastra: cuenta de nuevo
    assert d.actualizar(8, True, (0.5, 2.0)) is None
    assert d.actualizar(9, True, (0.5, 2.0))["activo"] is True


def test_caida_breve_no_es_desmayo():
    d = DetectorDesmayo(inmovil_s=5)
    d.actualizar(0, True, (0, 2))
    assert d.actualizar(3, False, None) is None


# -- aforo -------------------------------------------------------------------
def test_aforo_suaviza_parpadeo_y_republica():
    a = Aforo(ventana=5, republicar_s=5)
    pubs = [a.actualizar(t, n) for t, n in enumerate([3, 3, 3, 0, 3, 3, 4, 4, 4])]
    assert 0 not in pubs                       # un frame sin detecciones no vacía el refugio
    assert pubs[0] == 3 and 4 in pubs
    assert a.actualizar(100, 4) == 4           # republica pasado el plazo aunque no cambie


def test_estado_por_forma_de_caja():
    assert estado_caja((0, 0, 50, 170)) == "de_pie"
    assert estado_caja((0, 0, 90, 100)) == "sentado"
    assert estado_caja((0, 0, 170, 60)) == "suelo"


def _cuadro(prof_m: float | None):
    bgr = np.zeros((480, 640, 3), np.uint8)
    prof = None if prof_m is None else np.full((480, 640), int(prof_m * 1000), np.uint16)
    return Cuadro(bgr, prof, None if prof_m is None else (600.0, 600.0, 320.0, 240.0))


def test_personas_con_profundidad_y_filtro_de_calle():
    marco = MarcoHabitacion()
    dets = [Deteccion(7, (300, 100, 340, 300), 0.9)]
    p = personas(dets, _cuadro(3.0), marco)
    assert p[0]["etiqueta"] == "Persona 7" and p[0]["estado"] == "de_pie"
    assert abs(p[0]["x"]) < 0.3 and 2.0 < p[0]["y"] < 3.5
    assert personas(dets, _cuadro(9.0), marco) == []          # a 9 m = calle, no cuenta
    sin = personas([Deteccion(None, (0, 0, 10, 30), 0.5)], _cuadro(None), marco)
    assert sin[0]["x"] is None and sin[0]["etiqueta"] == "Persona ?"


def test_persona_cercana_asocia_desmayo_a_etiqueta():
    gente = [{"id": 2, "x": 0.0, "y": 2.0}, {"id": 5, "x": 1.5, "y": 3.0}, {"id": 9, "x": None, "y": None}]
    assert persona_cercana(gente, (1.4, 3.1)) == 5
    assert persona_cercana(gente, (5.0, 5.0)) is None


class _CapFalsa:
    def __init__(self, n):
        self.n = n

    def leer(self):
        if self.n == 0:
            return None
        self.n -= 1
        return _cuadro(3.0)

    def cerrar(self):
        pass


async def test_fuente_pose_cuenta_con_la_misma_camara():
    bus = Bus()
    bus.enlazar_loop(asyncio.get_running_loop())
    vistos = []
    bus.oyente(vistos.append)
    cont = lambda c: [Deteccion(1, (100, 100, 140, 300), .9), Deteccion(2, (400, 100, 440, 300), .9)]
    f = FuentePose("realsense", captura=_CapFalsa(6), estimador=lambda c: None, contador=cont, fps=100)
    await asyncio.wait_for(asyncio.to_thread(f._bucle, bus), 5)
    await asyncio.sleep(0.05)
    assert [e.valor for e in vistos if e.tipo == "aforo"][0] == 2
    ult = [e.valor for e in vistos if e.tipo == "personas"][-1]
    assert [p["etiqueta"] for p in ult] == ["Persona 1", "Persona 2"]
    assert all(e.fuente == "realsense" for e in vistos if e.tipo in ("aforo", "personas"))


# -- visión simulada -----------------------------------------------------------
def _correr_sim(s: FuenteVisionSim, segundos: float, dt: float = 0.5):
    evs, t = [], 0.0
    while t < segundos:
        evs += s.paso(t, dt)
        t += dt
    return evs


def test_sim_aforo_cuadra_con_personas_y_llega_el_bus():
    s = FuenteVisionSim(bus_s=30, semilla=3, inicial=2)
    evs = _correr_sim(s, 120)
    gente = [e.valor for e in evs if e.tipo == "personas"]
    aforos = [e.valor for e in evs if e.tipo == "aforo"]
    assert aforos[-1] == len(gente[-1])
    assert max(len(g) for g in gente) >= 6                    # el bus mete un grupo
    ids = [p["id"] for p in gente[-1]]
    assert len(ids) == len(set(ids)) and 1 in ids
    assert len(gente[-1]) <= 1 + len(BANCOS) + len(DE_PIE)


def test_sim_desmayo_de_persona_1():
    s = FuenteVisionSim(periodo_caida=10, inmovil_s=3, semilla=1)
    evs = _correr_sim(s, 30, dt=0.1)
    d = [e.valor for e in evs if e.tipo == "desmayo"]
    assert d[0]["activo"] is True and d[0]["persona"] == 1
    assert d[1]["activo"] is False                            # se levanta: se resuelve


def test_sim_obedece_aforo_del_panel():
    s = FuenteVisionSim(semilla=2, inicial=1, bus_s=1e9)
    s._oir(Evento("aforo", 12, "panel"))
    evs = _correr_sim(s, 1)
    assert [e.valor for e in evs if e.tipo == "aforo"][-1] == 12


async def test_conmutador_no_mezcla_aforo_de_camara_y_sim():
    bus = Bus()
    vistos = []
    bus.oyente(vistos.append)
    sim = FuenteVisionSim()
    c = Conmutador(bus, object(), sim, pedido="sim")
    c.proxy("camara").publicar(Evento("aforo", 9, "realsense"))
    c.proxy("sim").publicar(Evento("aforo", 4, "sim"))
    assert [e.valor for e in vistos if e.tipo == "aforo"] == [4]


# -- YOLO real (solo si hay modelo + ultralytics en local) -----------------------
def test_yolo_real_cuenta_personas_en_imagen():
    ul = pytest.importorskip("ultralytics")
    cv2 = pytest.importorskip("cv2")
    img = Path(ul.__file__).parent / "assets" / "bus.jpg"
    if not MODELO.exists() or not img.exists():
        pytest.skip("sin modelo o imagen de prueba")
    from vision.aforo import ContadorYolo
    dets = ContadorYolo()(Cuadro(cv2.imread(str(img))))
    assert len(dets) >= 3
