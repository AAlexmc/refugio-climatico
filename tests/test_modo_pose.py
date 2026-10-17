import asyncio

import numpy as np
from fastapi.testclient import TestClient

from servidor.app import crear_app
from vision.modo_pose import Conmutador
from vision.pose import Cuadro, FuentePose
from control.reglas import MotorReglas
from nucleo.bus import Bus
from nucleo.evento import Evento
from sim.pose_sim import FuentePoseSim


class Reloj:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def _pose(fuente):
    return Evento("pose", {"puntos": [[0, 0, 0]] * 33, "cadera_z": 0.9, "visible": True}, fuente)


def montar(pedido="camara"):
    bus = Bus()
    bus.enlazar_loop(asyncio.get_event_loop())
    vistos = []
    bus.oyente(vistos.append)
    reloj = Reloj()
    cam, sim = FuentePose("webcam"), FuentePoseSim()
    c = Conmutador(bus, cam, sim, pedido=pedido, reloj=reloj)
    return bus, vistos, reloj, cam, sim, c


def fuentes_de(vistos, tipo):
    return [e.fuente for e in vistos if e.tipo == tipo]


async def test_solo_publica_la_fuente_activa():
    bus, vistos, reloj, cam, sim, c = montar()
    pc, ps = c.proxy("camara"), c.proxy("sim")
    ps.publicar(_pose("sim"))                      # arranca en sim hasta ver frames
    pc.publicar(_pose("webcam"))                   # frame de cámara, filtrado
    assert fuentes_de(vistos, "pose") == ["sim"]
    c.evaluar()
    assert c.efectivo == "camara"
    pc.publicar(_pose("webcam")); ps.publicar(_pose("sim"))
    assert fuentes_de(vistos, "pose") == ["sim", "webcam"]
    # estado_fuente de la inactiva sí pasa
    ps.publicar(Evento("estado_fuente", {"conectada": True, "detalle": "x"}, "sim"))
    assert "estado_fuente" in [e.tipo for e in vistos]


async def test_publicar_desde_hilo_tambien_filtra():
    bus, vistos, reloj, cam, sim, c = montar()
    pc = c.proxy("camara")
    pc.publicar_desde_hilo(_pose("webcam"))
    await asyncio.sleep(0.02)
    assert fuentes_de(vistos, "pose") == []        # sim activa: la cámara solo cuenta frames
    c.evaluar()
    assert c.efectivo == "camara"
    pc.publicar_desde_hilo(_pose("webcam"))
    await asyncio.sleep(0.02)
    assert fuentes_de(vistos, "pose") == ["webcam"]


async def test_autorrespaldo_sin_frames_y_vuelta():
    bus, vistos, reloj, cam, sim, c = montar()
    pc = c.proxy("camara")
    pc.publicar(_pose("webcam")); c.evaluar()
    assert c.efectivo == "camara"
    reloj.t += 4.9; c.evaluar()
    assert c.efectivo == "camara"
    reloj.t += 0.3; c.evaluar()                    # >5 s sin frames
    assert c.efectivo == "sim" and c.estado()["auto"] is True
    al = [e.valor for e in vistos if e.tipo == "alerta"]
    assert al == [{"nivel": "info", "codigo": "camara", "mensaje": "Cámara no disponible: modo simulación"}]
    reloj.t += 10; c.evaluar()
    assert len([e for e in vistos if e.tipo == "alerta"]) == 1     # no repite
    pc.publicar(_pose("webcam")); c.evaluar()      # la cámara vuelve y se pidió cámara
    assert c.efectivo == "camara"
    assert [e.valor["mensaje"] for e in vistos if e.tipo == "alerta"][-1].startswith("Cámara recuperada")
    modos = [e.valor["modo"] for e in vistos if e.tipo == "modo_pose"]
    assert modos == ["camara", "sim", "camara"]


async def test_camara_nunca_vista_cae_a_sim_tras_gracia_con_alerta():
    bus, vistos, reloj, cam, sim, c = montar()
    c.evaluar()
    assert c.efectivo == "sim" and not [e for e in vistos if e.tipo == "alerta"]
    reloj.t += 6; c.evaluar()
    assert [e.valor["codigo"] for e in vistos if e.tipo == "alerta"] == ["camara"]


async def test_pedido_sim_no_vuelve_solo_a_camara():
    bus, vistos, reloj, cam, sim, c = montar()
    pc = c.proxy("camara")
    pc.publicar(_pose("webcam")); c.evaluar()
    assert c.pedir("sim")["modo"] == "sim"
    for _ in range(3):
        pc.publicar(_pose("webcam")); c.evaluar()
    assert c.efectivo == "sim" and c.estado()["auto"] is False
    assert not [e for e in vistos if e.tipo == "alerta"]
    assert c.pedir("camara")["modo"] == "camara"


async def test_pedir_camara_sin_camara_se_queda_en_sim():
    bus, vistos, reloj, cam, sim, c = montar(pedido="sim")
    assert c.pedir("camara")["modo"] == "sim"
    assert c.estado()["auto"] is True


async def test_conmutar_sincroniza_estado_de_caida():
    bus, vistos, reloj, cam, sim, c = montar()
    motor = MotorReglas(bus, avisar=lambda *a: None); bus.oyente(motor.procesar)
    pc, ps = c.proxy("camara"), c.proxy("sim")
    ps.publicar(Evento("caida", True, "sim"))      # sim activa: caída
    assert [e.valor for e in vistos if e.tipo == "caida"] == [True]
    pc.publicar(_pose("webcam")); c.evaluar()      # pasa a cámara (de pie): el bus debe levantarse
    assert c.efectivo == "camara"
    assert [e.valor for e in vistos if e.tipo == "caida"] == [True, False]
    assert [e.valor["nivel"] for e in vistos if e.tipo == "alerta"][-1] == "info"
    # caída de la cámara inactiva no se emite
    c.pedir("sim")
    pc.publicar(Evento("caida", True, "webcam"))
    assert [e.valor for e in vistos if e.tipo == "caida"] == [True, False]


async def test_caida_del_sim_sigue_a_su_avatar_con_proxy():
    """pose_sim a través del proxy: pose y caida salen juntos y en orden."""
    bus, vistos, reloj, cam, sim, c = montar(pedido="sim")
    ps = c.proxy("sim")
    sim.velocidad = 1.0
    t = 0.0
    while t < 60:
        for ev in sim.paso(t):
            ps.publicar(ev)
        t += 0.1
    cai = [e.valor for e in vistos if e.tipo == "caida"]
    assert cai[:2] == [True, False] or cai[:1] == [True]
    assert all(e.fuente == "sim" for e in vistos if e.tipo in ("pose", "caida"))


# -- servidor --------------------------------------------------------------
class CapturaFalsa:
    def leer(self):
        import time
        time.sleep(0.01)
        return Cuadro(np.zeros((48, 64, 3), np.uint8))


def _lm():
    lm = np.full((33, 3), 0.5)
    lm[0] = [0.5, 0.2, 0]
    lm[27] = lm[28] = [0.5, 0.8, 0]
    return lm


def test_api_modo_con_camara_inyectada(tmp_path):
    lm = _lm()
    app = crear_app([("webcam", {"camara": "webcam", "fps": 30, "captura": CapturaFalsa(),
                                 "estimador": lambda c: (lm, np.ones(33)),
                                 "calibracion_ruta": tmp_path / "c.json"}),
                     ("pose_sim", {})])
    with TestClient(app) as c:
        import time
        for _ in range(40):
            if c.get("/api/pose/modo").json()["modo"] == "camara":
                break
            time.sleep(0.1)
        m = c.get("/api/pose/modo").json()
        assert m["modo"] == "camara" and m["conmutable"] is True
        assert c.post("/api/pose/modo", json={"modo": "sim"}).json()["modo"] == "sim"
        assert c.post("/api/pose/modo", json={"modo": "raro"}).status_code == 422
        time.sleep(0.5)
        est = {(e["tipo"]): e for e in c.get("/api/estado").json()}
        assert est["modo_pose"]["valor"]["modo"] == "sim"
        assert est["pose"]["fuente"] == "sim"


def test_api_sin_camara_real_cae_a_sim_con_alerta(monkeypatch):
    import vision.modo_pose as mp
    import vision.pose as dp
    monkeypatch.setattr(dp, "REINTENTO_S", 0.05)
    monkeypatch.setattr(mp, "GRACIA_S", 0.2)

    def falla(*a, **k):
        raise RuntimeError("Device or resource busy")
    monkeypatch.setattr(dp, "CapturaRealSense", falla)
    monkeypatch.setattr(mp, "PERIODO_S", 0.05)
    app = crear_app([("realsense", {"camara": "realsense"}), ("pose_sim", {})])
    with TestClient(app) as c:
        import time
        time.sleep(1.0)
        assert c.get("/api/pose/modo").json() | {"camara_ok": 0} == {
            "modo": "sim", "pedido": "camara", "auto": True, "camara_ok": 0, "conmutable": True}
        est = {e["tipo"]: e for e in c.get("/api/estado").json()}
        assert est["pose"]["fuente"] == "sim"
        assert est["alerta"]["valor"]["mensaje"] == "Cámara no disponible: modo simulación"


async def test_alerta_camara_no_disponible_se_cierra_tras_pasar_por_sim_manual():
    bus, vistos, reloj, cam, sim, c = montar()
    pc = c.proxy("camara")
    reloj.t += 10
    c.evaluar()                                    # sin frames pasada la gracia: alerta
    c.pedir("sim")                                 # el usuario pasa por sim manual
    pc.publicar(_pose("webcam"))                   # la cámara vuelve mientras tanto
    c.pedir("camara")
    assert c.efectivo == "camara"
    msgs = [e.valor["mensaje"] for e in vistos if e.tipo == "alerta" and e.valor["codigo"] == "camara"]
    assert msgs[0].startswith("Cámara no disponible") and msgs[-1].startswith("Cámara recuperada")


async def test_publicar_desde_hilo_filtra_en_el_loop():
    import threading
    bus, vistos, reloj, cam, sim, c = montar()
    hilos = []
    orig = c._deja_pasar
    c._deja_pasar = lambda rol, ev: (hilos.append(threading.current_thread()), orig(rol, ev))[1]
    t = threading.Thread(target=lambda: c.proxy("camara").publicar_desde_hilo(_pose("webcam")))
    t.start(); t.join()
    assert hilos == []                             # nada filtrado en el hilo
    await asyncio.sleep(0.02)
    assert hilos == [threading.main_thread()]
