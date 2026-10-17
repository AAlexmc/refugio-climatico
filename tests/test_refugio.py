"""Base del refugio: sim clima + aforo + reglas en lazo cerrado."""
from control.reglas import MotorReglas
from nucleo.bus import Bus
from nucleo.evento import Evento
from sim.aforo_sim import FuenteAforoSim
from sim.clima import FuenteClimaSim


def montar(**kw):
    bus = Bus()
    avisos = []
    m = MotorReglas(bus, avisar=lambda r, msg: avisos.append((r, msg)), **kw)
    bus.oyente(m.procesar)
    vistos = []
    bus.oyente(vistos.append)
    return bus, avisos, vistos


def cmds(vistos, destino):
    return [e.valor["valor"] for e in vistos if e.tipo == "comando" and e.valor["destino"] == destino]


def medir(bus, **v):
    for k, x in v.items():
        bus.publicar(Evento(k, x, "sim"))


def test_calor_fuera_cierra_claraboya_y_enciende_ac():
    bus, _, vistos = montar()
    medir(bus, temp_ext=35.0, temp=31.0, humedad=50.0)
    assert cmds(vistos, "claraboya")[-1] == 0.0
    assert cmds(vistos, "ac")[-1] is True


def test_noche_fresca_ventila_sin_ac():
    bus, _, vistos = montar()
    medir(bus, temp_ext=22.0, temp=28.0, humedad=50.0)
    assert cmds(vistos, "claraboya")[-1] == 1.0
    assert cmds(vistos, "ac")[-1] is False


def test_lluvia_cierra_claraboya():
    bus, _, vistos = montar()
    medir(bus, temp_ext=22.0, temp=28.0, humedad=50.0, lluvia=True)
    assert cmds(vistos, "claraboya")[-1] == 0.0


def test_nebulizador_solo_con_gente_y_aire_seco():
    bus, _, vistos = montar(aforo_max=20)
    medir(bus, temp_ext=35.0, temp=30.0, humedad=45.0, aforo=16)
    assert cmds(vistos, "nebulizador")[-1] is True
    medir(bus, humedad=70.0)
    assert cmds(vistos, "nebulizador")[-1] is False   # con HR alta empeora el índice de calor


def test_desmayo_avisa_una_vez_y_se_resuelve():
    bus, avisos, vistos = montar()
    medir(bus, desmayo={"activo": True})
    medir(bus, desmayo={"activo": True})
    assert len(avisos) == 1
    medir(bus, desmayo={"activo": False})
    niveles = [e.valor["nivel"] for e in vistos if e.tipo == "alerta" and e.valor["codigo"] == "desmayo"]
    assert niveles == ["critico", "info"]


def test_comandos_solo_en_cambios():
    bus, _, vistos = montar()
    for _ in range(5):
        medir(bus, temp_ext=35.0, temp=31.0, humedad=50.0)
    assert cmds(vistos, "ac") == [True]


def test_sim_obedece_comandos_y_enfria():
    f = FuenteClimaSim(inicio_hora=15)
    caliente = f.paso(3600)["temp"]
    f._oir(Evento("comando", {"destino": "ac", "valor": True}, "reglas"))
    assert f.paso(3600)["temp"] < caliente


def test_sim_placas_cargan_bateria_de_dia_y_descargan_de_noche():
    f = FuenteClimaSim(inicio_hora=10)
    b0 = f.bateria
    d = f.paso(3 * 3600)
    assert d["solar"] > 0 and d["bateria"] > b0
    f.t_s = 22 * 3600.0
    b1 = f.bateria
    d = f.paso(2 * 3600)
    assert d["solar"] == 0 and d["bateria"] < b1


def test_sim_estable_con_paso_grande():
    f = FuenteClimaSim(inicio_hora=0)
    for _ in range(48):
        d = f.paso(3600)
        assert -10 < d["temp"] < 90 and 0 <= d["bateria"] <= 100


def test_aforo_sim_acotado_y_obedece_inyeccion():
    a = FuenteAforoSim(maximo=20, semilla=1)
    assert all(0 <= a.paso() <= 26 for _ in range(500))
    a._oir(Evento("aforo", 12, "panel"))
    assert abs(a.paso() - 12) <= 10


def test_api_kits_sirve_catalogo():
    from fastapi.testclient import TestClient
    from servidor.app import crear_app
    with TestClient(crear_app([])) as c:
        d = c.get("/api/kits").json()
    assert {k["id"] for k in d["kits"]} == {"parada_bus", "terraza_comunitaria", "terraza_privada"}
    assert d["material_por_defecto"] in {m["id"] for m in d["materiales_cubierta"]}
