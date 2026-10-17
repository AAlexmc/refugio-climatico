"""Escenario 5 días: calle / cúpula sin control / OASI."""
import time

from sim import metricas

SERIES = {"t", "temp_calle", "temp_oasi", "temp_cupula", "solar", "consumo", "bateria", "aforo",
          "t_aparente_oasi", "t_aparente_calle", "caudal_m3h", "viento"}   # física del pabellón
RESUMEN = {"grados_reducidos_pico", "horas_riesgo_evitadas", "kwh_solares", "pct_autoconsumo",
           "autonomia_h", "coste_eur_dia", "co2_kg_evitado", "materiales", "kits"}


def test_forma_y_longitudes():
    d = metricas.escenario()
    assert set(d["series"]) == SERIES and set(d["resumen"]) == RESUMEN
    assert len({len(v) for v in d["series"].values()}) == 1
    assert len(d["series"]["t"]) == 5 * 144


def test_oasi_mas_fresco_que_calle_en_el_pico():
    d = metricas.escenario()
    s = d["series"]
    i = max(range(len(s["t"])), key=lambda k: s["temp_calle"][k])
    assert s["temp_oasi"][i] < s["temp_calle"][i]
    assert d["resumen"]["grados_reducidos_pico"] > 0


def test_cupula_sin_control_es_invernadero():
    s = metricas.escenario()["series"]
    assert max(s["temp_cupula"]) > max(s["temp_oasi"])


def test_bateria_en_rango_y_aforo():
    s = metricas.escenario()["series"]
    assert all(0 <= b <= 100 for b in s["bateria"])
    assert max(s["aforo"]) == 9 and min(s["aforo"]) == 2   # pabellón 6 × 2,4 m: 9 plazas (1,5 m²/persona)


def test_rapido_y_determinista():
    t0 = time.time()
    a = metricas._simular()
    assert time.time() - t0 < 5
    assert a == metricas.escenario()


def test_api_metricas():
    from fastapi.testclient import TestClient
    from servidor.app import crear_app
    with TestClient(crear_app([])) as c:
        d = c.get("/api/metricas").json()
    assert set(d["series"]) == SERIES
