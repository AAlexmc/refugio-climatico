"""FuenteClimaSim reescalada por evento `modulos` (kit, nº módulos, cubierta, tipo)."""
from nucleo.evento import Evento
from sim import clima, metricas


def _fuente(**mod):
    f = clima.FuenteClimaSim(inicio_hora=12.0)
    if mod:
        f._oir(Evento("modulos", mod, "sim", f.refugio))
    return f


def _correr(f, pasos=60):
    for _ in range(pasos):
        out = f.paso(600.0)
    return out


def test_defecto_intacto():
    f = clima.FuenteClimaSim()
    assert (f.area_fv, f.bat_kwh, f.ac_frio_w, f.g_solar) == (clima.AREA_FV, clima.BAT_KWH, clima.AC_FRIO_W, clima.G_SOLAR)
    assert not f.abierto


def test_n2_equivale_al_defecto_y_n4_duplica():
    f2, f4 = _fuente(kit="parada_bus", n=2, area_m2=18), _fuente(kit="parada_bus", n=4, area_m2=36)
    assert f2.area_fv == clima.AREA_FV and f2.bat_kwh == clima.BAT_KWH
    assert f4.area_fv == 2 * f2.area_fv and f4.bat_kwh == 2 * f2.bat_kwh
    assert f4.ac_frio_w == 2 * f2.ac_frio_w
    assert _correr(_fuente(n=4))["solar"] == 2 * _correr(_fuente(n=2))["solar"]


def test_cubierta_g_efectivo():
    assert abs(_fuente(n=2, cubierta="vidrio_control_solar").g_solar - 0.29 * 0.45) < 1e-9
    assert abs(_fuente(n=2, cubierta="policarbonato_opal_ir").g_solar - 0.30 * 0.45) < 1e-9  # g null


def test_vidrio_simple_mas_caliente():
    a = _correr(_fuente(n=2, cubierta="vidrio_simple"), 40)["temp"]
    b = _correr(_fuente(n=2, cubierta="vidrio_control_solar"), 40)["temp"]
    assert a > b
    m = metricas.escenario()["resumen"]["materiales"]
    assert m["vidrio_simple"] > m["vidrio_control_solar"]


def test_arbol_solar_sin_ac_y_a_la_sombra():
    f = _fuente(kit="arbol", n=1, tipo="arbol_solar")
    f.ac = True
    out = f.paso(30.0)
    te = out["temp_ext"]
    assert out["temp"] == round(te - clima.DT_SOMBRA, 2)
    assert out["potencia"] == 150     # el AC no consume
    f.nebulizador = True
    assert f.paso(30.0)["temp"] <= te - clima.DT_SOMBRA


def test_bloque_kits():
    k = metricas.escenario()["resumen"]["kits"]
    assert set(k) == {"parada_bus", "terraza_comunitaria", "terraza_privada"}
    assert k["terraza_comunitaria"]["kwh_solares_dia"] > k["terraza_privada"]["kwh_solares_dia"]
