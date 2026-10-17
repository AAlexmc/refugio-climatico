"""Física del Pabellón Venturi: órdenes de magnitud y signos."""
import math

from sim.fisica_pabellon import (Pabellon, bulbo_humedo, caudal, enfriamiento_evaporativo,
                                 pabellon_de_modulos, presion_chimenea, presion_venturi,
                                 temperatura_aparente)


def test_geometria_6m():
    p = pabellon_de_modulos(2)
    assert p.largo == 6.0
    assert 55 < p.volumen < 60                     # 39,6 m³ caja + 17,2 m³ bóveda
    assert p.extractores == 3 and p.boquillas == 8


def test_venturi_bernoulli():
    # 4 m/s -> ½·1,2·16·1,56 ≈ 15 Pa de succión
    assert math.isclose(presion_venturi(4.0), 14.98, rel_tol=0.01)
    assert presion_venturi(0.0) == 0.0


def test_chimenea_signo():
    p = Pabellon()
    assert presion_chimenea(p, 32, 30) > 0         # dentro más caliente: el aire sube
    assert presion_chimenea(p, 28, 30) < 0
    assert 0.2 < presion_chimenea(p, 33, 30) < 0.6  # 3 K en 3,95 m ≈ 0,46 Pa


def test_caudal_crece_con_viento_y_apertura():
    p = Pabellon()
    q0 = caudal(p, 30, 30, 0.0, 1.0, False)["caudal"]
    q4 = caudal(p, 30, 30, 4.0, 1.0, False)["caudal"]
    cerrado = caudal(p, 30, 30, 4.0, 0.0, False)["caudal"]
    assert q0 == 0 and q4 > 1.0                    # >3600 m³/h con brisa de 4 m/s
    assert cerrado < 0.01                          # garganta cerrada: casi nada
    assert caudal(p, 30, 30, 0.0, 0.0, True)["caudal"] == 3 * 0.30


def test_renovaciones_razonables():
    r = caudal(Pabellon(), 31, 30, 3.0, 1.0, False)["renovaciones_h"]
    assert 30 < r < 300                            # ventilación natural intensa, no absurda


def test_bulbo_humedo_stull():
    assert abs(bulbo_humedo(20, 50) - 13.7) < 0.3  # valor de referencia de Stull (2011)
    assert bulbo_humedo(35, 30) < 35


def test_evaporativo_limitado_por_bulbo_humedo():
    p = Pabellon()
    seco = enfriamiento_evaporativo(p, 2.0, 35, 30, True)
    humedo = enfriamiento_evaporativo(p, 2.0, 35, 95, True)
    assert seco > humedo >= 0
    assert enfriamiento_evaporativo(p, 2.0, 35, 30, False) == 0
    assert seco <= p.boquillas * 3.8 / 3600 * 2.45e6 + 1e-6


def test_aire_en_movimiento_baja_sensacion():
    assert temperatura_aparente(32, 50, 1.0) < temperatura_aparente(32, 50, 0.0)
    assert temperatura_aparente(32, 80, 0.0) > temperatura_aparente(32, 40, 0.0)


def test_ampliar_largo_y_ancho():
    from sim.fisica_pabellon import pabellon
    a, b = pabellon(6, 2.4), pabellon(12, 4.8)
    assert b.largo == 12 and b.ancho == 4.8 and math.isclose(b.radio, 2.55)
    assert b.volumen > 3.5 * a.volumen and b.extractores == 6
    assert pabellon(6.9, 2.9).largo == 6.0 and pabellon(6.9, 2.9).ancho == 2.4   # tramos discretos


def test_metricas_dia_por_geometria():
    from sim.metricas import dia
    r = dia(8, 3.6)
    s = r["series"]
    assert len(s["t"]) == 144 and len(s["t_aparente_oasi"]) == 144
    assert r["pabellon"]["largo"] == 8 and r["pabellon"]["ancho"] == 3.6
    assert max(s["temp_calle"]) - max(s["temp_oasi"]) > 3        # el pabellón refresca en el pico
