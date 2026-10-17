import asyncio
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from servidor.app import crear_app
from vision import calibracion
from vision.caidas import DetectorCaidas, Umbrales
from vision.calibracion import ErrorCalibracion, calcular, cargar, guardar, mediana, validar
from vision.pose import Cuadro, FuentePose
from control.reglas import MotorReglas
from nucleo.bus import Bus
from test_caidas import DT, correr, de_pie, pose, rampa

PIE = {"cadera_z": 1.00, "angulo": 5.0}
SUELO = {"cadera_z": 0.20, "angulo": 80.0}


# -- cálculo ---------------------------------------------------------------
def test_calcular_umbrales_entre_medianas():
    u, nota = calcular(PIE, SUELO)
    assert u.cadera_suelo == pytest.approx(0.20 + 0.35 * 0.80)
    assert u.cadera_levantado == pytest.approx(0.20 + 0.65 * 0.80)
    assert u.angulo_torso == pytest.approx(61.25, abs=0.1)   # ap + 0.75*(as-ap), min 60
    assert u.exigir_descenso is True and "DESACTIVADO" not in nota


def test_calcular_suelo_sentado_se_rechaza():
    with pytest.raises(ErrorCalibracion, match="túmbate en el suelo, no te sientes"):
        calcular(PIE, {"cadera_z": 0.30, "angulo": 15.0})


def test_calcular_angulo_acotado():
    u, _ = calcular(PIE, {"cadera_z": 0.20, "angulo": 90.0})
    assert u.angulo_torso <= 75.0
    u, _ = calcular({"cadera_z": 1.0, "angulo": 20.0}, {"cadera_z": 0.2, "angulo": 55.0})
    assert u.angulo_torso == 60.0


def _aprendidos():
    return calcular(PIE, SUELO)[0]


def test_silla_rapida_no_es_caida_con_umbrales_aprendidos():
    serie = de_pie(2) + rampa(0.95, 0.48, 0, 5, 0.8) + [(0.48, 5)] * 50
    assert correr(DetectorCaidas(_aprendidos()), serie) == []


def test_cuclillas_no_es_caida_con_umbrales_aprendidos():
    serie = de_pie(2) + rampa(0.95, 0.38, 0, 50, 0.5) + [(0.38, 50)] * 30
    assert correr(DetectorCaidas(_aprendidos()), serie) == []


def test_tumbado_si_es_caida_con_umbrales_aprendidos():
    serie = de_pie(2) + rampa(0.95, 0.2, 0, 85, 0.5) + [(0.2, 85)] * 20
    assert [c for _, c in correr(DetectorCaidas(_aprendidos()), serie)] == [True]


def test_validar_permite_cadera_negativa_relativa_al_marco():
    u = validar({"cadera_suelo": -0.2, "cadera_levantado": 0.3})
    assert u.cadera_suelo == -0.2
    with pytest.raises(ErrorCalibracion):
        validar({"cadera_suelo": 0.3, "cadera_levantado": -0.2})


@pytest.mark.parametrize("v", ["false", 0, 1, None])
def test_validar_exigir_descenso_estricto(v):
    with pytest.raises(ErrorCalibracion, match="exigir_descenso"):
        validar({"cadera_suelo": 0.3, "cadera_levantado": 0.6, "exigir_descenso": v})


def test_calcular_hueco_pequeno_error_claro():
    with pytest.raises(ErrorCalibracion, match="recoloca la cámara"):
        calcular(PIE, {"cadera_z": 0.90, "angulo": 80.0})


def test_mediana_pocas_muestras():
    with pytest.raises(ErrorCalibracion, match="no veo"):
        mediana([(1.0, 3.0)] * 2)
    m = mediana([(1.0, 3.0), (1.2, 5.0), (0.8, 4.0), (1.0, 4.0), (1.1, 4.0)])
    assert m["cadera_z"] == 1.0 and m["angulo"] == 4.0 and m["muestras"] == 5


@pytest.mark.parametrize("d", [
    {}, {"cadera_suelo": 0.8, "cadera_levantado": 0.5}, {"cadera_suelo": "x", "cadera_levantado": 1},
    {"cadera_suelo": 0.3, "cadera_levantado": 0.6, "angulo_torso": 2},
    {"cadera_suelo": 0.3, "cadera_levantado": 0.6, "suelo_sostenido_s": 0},
])
def test_validar_rechaza_incoherente(d):
    with pytest.raises(ErrorCalibracion):
        validar(d)


# -- persistencia ----------------------------------------------------------
def test_guardar_cargar_atomico(tmp_path):
    ruta = tmp_path / "sub" / "c.json"
    u = Umbrales(0.4, 0.7, None, 1.0, False)
    guardar(u, ruta)
    assert cargar(ruta) == u
    assert not list(ruta.parent.glob("*.tmp"))
    assert json.loads(ruta.read_text())["angulo_torso"] is None


def test_cargar_ausente_o_roto_da_none(tmp_path):
    assert cargar(tmp_path / "no.json") is None
    (tmp_path / "roto.json").write_text("{no json")
    assert cargar(tmp_path / "roto.json") is None
    (tmp_path / "incoh.json").write_text('{"cadera_suelo": 2, "cadera_levantado": 1}')
    assert cargar(tmp_path / "incoh.json") is None


# -- detector con umbrales -------------------------------------------------
def test_detector_defaults_intactos():
    assert DetectorCaidas().umbrales == Umbrales(0.45, 0.70, 60.0, 1.0, True)


def test_modo_demo_no_exige_descenso():
    # tumbarse despacio (6 s): sin descenso rápido nunca arma el detector
    lento = de_pie(1) + rampa(0.95, 0.2, 0, 85, 6.0) + [(0.2, 85)] * 30
    assert correr(DetectorCaidas(), lento) == []
    assert [c for _, c in correr(DetectorCaidas(Umbrales(exigir_descenso=False)), lento)] == [True]


def test_umbrales_aprendidos_detectan_con_marco_desplazado():
    # cámara mal colocada: de pie la cadera sale a 1.0 y en el suelo a 0.55 (> 0.45 por defecto)
    u, _ = calcular({"cadera_z": 1.0, "angulo": 5.0}, {"cadera_z": 0.55, "angulo": 85.0})
    serie = de_pie(2) + rampa(1.0, 0.55, 5, 85, 0.5) + [(0.55, 85)] * 20
    assert correr(DetectorCaidas(), serie) == []
    assert [c for _, c in correr(DetectorCaidas(u), serie)] == [True]


def test_sin_criterio_de_angulo_decide_la_cadera():
    u = Umbrales(angulo_torso=None)
    serie = de_pie(2) + rampa(0.95, 0.3, 0, 10, 0.5) + [(0.3, 10)] * 20   # sentado en el suelo
    assert correr(DetectorCaidas(), serie) == []
    assert [c for _, c in correr(DetectorCaidas(u), serie)] == [True]


# -- FuentePose ------------------------------------------------------------
class CapturaFalsa:
    def leer(self):
        return Cuadro(np.zeros((48, 64, 3), np.uint8))


def test_fuente_carga_json_al_arrancar_y_aplica_en_caliente(tmp_path):
    ruta = tmp_path / "c.json"
    guardar(Umbrales(0.33, 0.66, None), ruta)
    f = FuentePose("webcam", calibracion_ruta=ruta)
    assert f.umbrales.cadera_suelo == 0.33
    f.aplicar_umbrales(Umbrales(0.5, 0.8))
    assert f._detector.umbrales.cadera_levantado == 0.8


def test_fuente_sin_json_usa_defaults():
    assert FuentePose("webcam").umbrales == Umbrales()


async def test_grabar_recoge_solo_poses_visibles():
    bus = Bus()
    bus.enlazar_loop(asyncio.get_running_loop())
    f = FuentePose("webcam")

    async def alimentar():
        for k in range(30):
            f._publicar(bus, k * DT, pose(1.0, 5.0) if k % 3 else None)
            await asyncio.sleep(0.01)
    t = asyncio.create_task(alimentar())
    muestras = await f.grabar(0.2)
    await t
    assert 5 <= len(muestras) < 30
    m = mediana(muestras)
    assert m["cadera_z"] == pytest.approx(1.0) and m["angulo"] == pytest.approx(5.0, abs=0.1)
    assert f._grabador.activo is False
    assert f.vivo["estado"] in ("de_pie", "sin_persona")


async def test_estado_vivo_de_pie_suelo_caida():
    bus = Bus()
    bus.enlazar_loop(asyncio.get_running_loop())
    f = FuentePose("webcam")
    f._publicar(bus, 0.0, pose(1.0, 3.0))
    assert f.vivo["estado"] == "de_pie"
    f._publicar(bus, 0.1, pose(0.2, 85.0))
    assert f.vivo["estado"] == "suelo"
    f._publicar(bus, 0.2, None)
    assert f.vivo["estado"] == "sin_persona" and f.vivo["visible"] is False


async def test_caida_de_camara_dispara_alerta_y_evento_igual_que_la_simulada():
    """FuentePose -> bus -> MotorReglas: mismo evento `caida` que consumen
    panel.js/twin2.js (robot acude) y la misma alerta de aviso `caida` que pose_sim."""
    bus = Bus()
    bus.enlazar_loop(asyncio.get_running_loop())
    motor = MotorReglas(bus, avisar=lambda *a: None)
    bus.oyente(motor.procesar)
    vistos = []
    bus.oyente(vistos.append)
    f = FuentePose("realsense", refugio="R1")
    serie = de_pie(2) + rampa(0.95, 0.2, 0, 85, 0.5) + [(0.2, 85)] * 20
    for k, e in enumerate(serie):
        f._publicar(bus, k * DT, pose(*e))
    await asyncio.sleep(0.05)   # publicar_desde_hilo vuelve por call_soon_threadsafe
    caidas = [e for e in vistos if e.tipo == "caida"]
    assert [(e.valor, e.refugio) for e in caidas] == [(True, "R1")]
    al = [e.valor for e in vistos if e.tipo == "alerta"]
    assert al and al[-1]["nivel"] == "aviso" and al[-1]["codigo"] == "caida"


# -- API -------------------------------------------------------------------
def _app(tmp_path, persona=True, **kw):
    lm = np.full((33, 3), 0.5)
    lm[0] = [0.5, 0.2, 0]
    lm[27] = lm[28] = [0.5, 0.8, 0]
    est = (lambda c: (lm, np.ones(33))) if persona else (lambda c: None)
    return crear_app([("webcam", {"camara": "webcam", "fps": 50, "captura": CapturaFalsa(),
                                  "estimador": est,
                                  "calibracion_ruta": tmp_path / "cal.json"})], **kw)


def test_api_calibracion_ciclo_completo(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        g = c.get("/api/caida/calibracion").json()
        assert g["guardada"] is False and g["umbrales"] == g["defaults"]
        r = c.post("/api/caida/calcular", json={"pie": PIE, "suelo": SUELO, "exigir_descenso": False})
        u = r.json()["umbrales"]
        assert r.status_code == 200 and u["exigir_descenso"] is False and r.json()["nota"]
        assert c.post("/api/caida/calibracion", json=u).json()["ok"]
        assert json.loads((tmp_path / "cal.json").read_text())["cadera_suelo"] == u["cadera_suelo"]
        assert c.get("/api/caida/calibracion").json()["guardada"] is True
        assert c.get("/api/caida/vivo").json()["umbrales"]["cadera_suelo"] == u["cadera_suelo"]
        assert c.delete("/api/caida/calibracion").json()["ok"]
        assert not (tmp_path / "cal.json").exists()
        assert c.get("/api/caida/calibracion").json()["umbrales"] == g["defaults"]


def test_api_errores(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        r = c.post("/api/caida/calcular", json={"pie": PIE, "suelo": {"cadera_z": 0.95, "angulo": 80}})
        assert r.status_code == 422 and "recoloca la cámara" in r.json()["detail"]
        assert c.post("/api/caida/calibracion", json={"cadera_suelo": 1, "cadera_levantado": 0.5}
                      ).status_code == 422
        assert c.post("/api/caida/grabar", json={"clase": "volando"}).status_code == 422
        r = c.post("/api/caida/grabar", json={"clase": "de_pie", "segundos": 0.3})
        assert r.status_code == 200 and r.json()["muestras"] >= 5


def test_api_grabar_sin_persona_da_error_claro(tmp_path):
    with TestClient(_app(tmp_path, persona=False)) as c:
        r = c.post("/api/caida/grabar", json={"clase": "suelo", "segundos": 0.3})
        assert r.status_code == 422 and "no veo" in r.json()["detail"]


def test_api_sin_camara():
    with TestClient(crear_app([])) as c:
        assert c.get("/api/caida/vivo").status_code == 409
        assert c.post("/api/caida/grabar", json={"clase": "suelo"}).status_code == 409
        assert c.get("/api/caida/calibracion").status_code == 200
        assert c.get("/api/pose/modo").json()["conmutable"] is False
        assert c.post("/api/pose/modo", json={"modo": "sim"}).status_code == 409


def test_api_calcular_valida_y_estricto(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        # cadera fuera de rango (> 3 m): guardar lo rechazaría, calcular también
        r = c.post("/api/caida/calcular", json={"pie": {"cadera_z": 3.5, "angulo": 5},
                                                "suelo": {"cadera_z": 2.5, "angulo": 80}})
        assert r.status_code == 422 and "cadera_levantado" in r.json()["detail"]
        r = c.post("/api/caida/calcular", json={"pie": PIE, "suelo": SUELO, "exigir_descenso": "false"})
        assert r.status_code == 422 and "exigir_descenso" in r.json()["detail"]
        # alturas relativas al marco: suelo negativo vale
        r = c.post("/api/caida/calcular", json={"pie": {"cadera_z": 0.4, "angulo": 5},
                                                "suelo": {"cadera_z": -0.4, "angulo": 80}})
        assert r.status_code == 200
        assert c.post("/api/caida/calibracion", json=r.json()["umbrales"]).status_code == 200
        r = c.post("/api/caida/calcular", json={"pie": PIE, "suelo": {"cadera_z": 0.3, "angulo": 15}})
        assert r.status_code == 422 and "no te sientes" in r.json()["detail"]
