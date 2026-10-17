"""Reglas de control 2A·H1: entrada -> comando/alerta exacta."""
from control.reglas import MotorReglas
from nucleo.bus import Bus
from nucleo.evento import Evento

RELOJ = [0.0]


def montar():
    bus = Bus()
    avisos = []
    m = MotorReglas(bus, avisar=lambda r, msg: avisos.append((r, msg)), reloj=lambda: RELOJ[0])
    bus.oyente(m.procesar)
    vistos = []
    bus.oyente(vistos.append)
    return bus, avisos, vistos


def medir(bus, **v):
    for k, x in v.items():
        bus.publicar(Evento(k, x, "sim"))


def cmds(vistos, destino):
    return [e.valor["valor"] for e in vistos if e.tipo == "comando" and e.valor["destino"] == destino]


def al(vistos, codigo):
    return [(e.valor["nivel"], e.valor["mensaje"]) for e in vistos if e.tipo == "alerta" and e.valor["codigo"] == codigo]


def atendido(bus):
    bus.publicar(Evento("comando", {"destino": "atendido", "valor": "desmayo"}, "panel"))


def test_caida_sola_es_aviso_sin_061():
    bus, avisos, vistos = montar()
    medir(bus, caida=True)
    assert al(vistos, "caida") == [("aviso", "Persona en el suelo")]
    assert al(vistos, "desmayo") == [] and avisos == []
    medir(bus, caida=False)
    assert [n for n, _ in al(vistos, "caida")] == ["aviso", "info"]


def test_desmayo_critico_con_persona_y_aforo():
    bus, avisos, vistos = montar()
    medir(bus, aforo=7, desmayo={"activo": True, "persona": "p3"})
    assert al(vistos, "desmayo")[-1][0] == "critico"
    assert len(avisos) == 1 and "p3" in avisos[0][1] and "aforo actual: 7" in avisos[0][1]


def test_desmayo_sin_persona_no_rompe():
    bus, avisos, _ = montar()
    medir(bus, desmayo={"activo": True})
    assert len(avisos) == 1 and "aforo actual: 0" in avisos[0][1]


def test_atendido_baja_a_aviso_y_no_vuelve_a_critico_hasta_reactivar():
    bus, avisos, vistos = montar()
    medir(bus, desmayo={"activo": True, "persona": "p1"})
    atendido(bus)
    assert al(vistos, "desmayo")[-1] == ("aviso", "Atendido por el equipo médico")
    medir(bus, desmayo={"activo": True, "persona": "p1"}, caida=True)
    assert [n for n, _ in al(vistos, "desmayo")] == ["critico", "aviso"]
    assert len(avisos) == 1
    medir(bus, desmayo={"activo": False})
    medir(bus, desmayo={"activo": True})
    assert [n for n, _ in al(vistos, "desmayo")] == ["critico", "aviso", "info", "critico"]
    assert len(avisos) == 2


def test_atendido_sin_desmayo_activo_no_se_arrastra_y_ignora_fuente_reglas():
    bus, avisos, vistos = montar()
    atendido(bus)
    medir(bus, desmayo={"activo": True})
    assert al(vistos, "desmayo")[-1][0] == "critico"
    bus.publicar(Evento("comando", {"destino": "atendido", "valor": "desmayo"}, "reglas"))
    assert al(vistos, "desmayo")[-1][0] == "critico"
    bus.publicar(Evento("comando", {"destino": "ac", "valor": True}, "panel"))
    assert al(vistos, "desmayo")[-1][0] == "critico"


def test_publica_indice_calor_redondeado_solo_en_cambios():
    bus, _, vistos = montar()
    for _ in range(3):
        medir(bus, temp=30.0, humedad=50.0)
    ic = [e for e in vistos if e.tipo == "indice_calor"]
    assert len(ic) == 1 and ic[0].valor == round(ic[0].valor, 1) and ic[0].fuente == "reglas"
    medir(bus, temp=31.0)
    assert len([e for e in vistos if e.tipo == "indice_calor"]) == 2


def test_alerta_calor_histeresis():
    bus, _, vistos = montar()
    medir(bus, temp=36.0, humedad=60.0)
    assert al(vistos, "calor")[-1][0] == "aviso"
    medir(bus, temp=24.0, humedad=40.0)
    assert al(vistos, "calor")[-1][0] == "info"


def test_bateria_baja_ahorro_sube_consigna_ac():
    bus, _, vistos = montar()
    medir(bus, temp_ext=35.0, temp=27.5, humedad=50.0)
    assert cmds(vistos, "ac")[-1] is True
    medir(bus, bateria=15.0)
    assert al(vistos, "bateria_baja")[-1][0] == "aviso"
    assert cmds(vistos, "ac")[-1] is False                # IC < 28 (umbral 29, histéresis 28)
    medir(bus, bateria=22.0)                              # banda muerta: sigue ahorro
    assert al(vistos, "bateria_baja")[-1][0] == "aviso"
    medir(bus, bateria=25.0)
    assert al(vistos, "bateria_baja")[-1][0] == "info"
    assert cmds(vistos, "ac")[-1] is True


def test_co2_alto_abre_claraboya_aunque_haga_calor_fuera():
    bus, _, vistos = montar()
    medir(bus, temp_ext=35.0, temp=30.0, humedad=50.0, co2=1200.0)
    assert cmds(vistos, "claraboya")[-1] == 0.6
    assert al(vistos, "co2")[-1][0] == "aviso"
    medir(bus, lluvia=True)
    assert cmds(vistos, "claraboya")[-1] == 0.0
    medir(bus, lluvia=False, co2=800.0)
    assert cmds(vistos, "claraboya")[-1] == 0.0
    assert al(vistos, "co2")[-1][0] == "info"


def test_claraboya_parcial():
    bus, _, vistos = montar()
    medir(bus, temp=28.0, humedad=50.0, temp_ext=26.0)    # 2 °C más fresco
    assert cmds(vistos, "claraboya")[-1] == 0.6
    medir(bus, temp_ext=25.0)                             # exactamente 3
    assert cmds(vistos, "claraboya")[-1] == 1.0
    medir(bus, temp_ext=27.5)                             # < 1 °C: cerrada
    assert cmds(vistos, "claraboya")[-1] == 0.0


def test_ahorro_solar_preenfria_un_grado():
    bus, _, vistos = montar()
    medir(bus, temp_ext=35.0, temp=26.5, humedad=50.0)
    assert cmds(vistos, "ac")[-1] is False
    medir(bus, bateria=95.0, solar=900.0, potencia=1000.0)
    assert cmds(vistos, "ac")[-1] is True                 # umbral 26
    medir(bus, solar=500.0)
    assert cmds(vistos, "ac")[-1] is True                 # histéresis 1 °C: sigue encendido hasta IC <= 26
