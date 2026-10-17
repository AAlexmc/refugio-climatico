import asyncio
import threading

import pytest
from fastapi.testclient import TestClient

from servidor.app import crear_app
from nucleo.bus import COLA_MAX, Bus
from nucleo.evento import Evento, alerta


def test_evento_unidad_canonica_y_roundtrip():
    ev = Evento("temp", 31.5, "esp32")
    assert ev.unidad == "°C"
    assert Evento.from_dict(ev.to_dict()) == ev


@pytest.mark.parametrize("kw", [
    {"tipo": "temperatura", "valor": 1, "fuente": "esp32"},
    {"tipo": "temp", "valor": 1, "fuente": "arduino"},
    {"tipo": "alerta", "valor": {"nivel": "grave"}, "fuente": "reglas"},
    {"tipo": "alerta", "valor": "caida", "fuente": "reglas"},
])
def test_evento_rechaza_mal_formado(kw):
    with pytest.raises(ValueError):
        Evento(**kw)


def test_alerta_atajo():
    a = alerta("critico", "caida", "P1 en el suelo")
    assert a.valor == {"nivel": "critico", "codigo": "caida", "mensaje": "P1 en el suelo"}


async def test_bus_reparte_y_guarda_ultimo():
    bus = Bus()
    bus.enlazar_loop(asyncio.get_running_loop())
    it = bus.suscribir().__aiter__()
    pendiente = asyncio.ensure_future(it.__anext__())
    await asyncio.sleep(0)
    bus.publicar(Evento("temp", 30.0, "sim"))
    bus.publicar(Evento("temp", 31.0, "sim"))
    assert (await pendiente).valor == 30.0
    assert bus.ultimo[("R1", "temp")].valor == 31.0
    await it.aclose()


async def test_bus_cola_llena_descarta_viejos_sin_bloquear():
    bus = Bus()
    it = bus.suscribir().__aiter__()
    pendiente = asyncio.ensure_future(it.__anext__())
    await asyncio.sleep(0)  # el generador registra su cola
    q = next(iter(bus._subs))
    pendiente.cancel()
    for i in range(COLA_MAX + 10):
        bus.publicar(Evento("temp", float(i), "sim"))
    assert q.qsize() == COLA_MAX
    assert q.get_nowait().valor == 10.0


async def test_bus_publicar_desde_hilo():
    bus = Bus()
    bus.enlazar_loop(asyncio.get_running_loop())
    vistos = []
    bus.oyente(vistos.append)
    th = threading.Thread(target=bus.publicar_desde_hilo, args=(Evento("humedad", 55.0, "esp32"),))
    th.start(); th.join()
    await asyncio.sleep(0.01)
    assert [e.valor for e in vistos] == [55.0]


def test_bus_desde_hilo_sin_loop_falla_claro():
    with pytest.raises(RuntimeError):
        Bus().publicar_desde_hilo(Evento("temp", 1.0, "sim"))


def test_server_evento_comando_estado_y_ws():
    app = crear_app([])
    with TestClient(app) as c:
        assert c.post("/api/evento", json={"tipo": "temp", "valor": 29.0, "fuente": "esp32"}).json() == {"ok": True}
        assert c.post("/api/evento", json={"tipo": "xx", "valor": 1, "fuente": "esp32"}).status_code == 422
        assert c.post("/api/comando", json={"destino": "rele"}).status_code == 422
        assert c.post("/api/comando", json={"destino": "rele", "valor": True}).status_code == 200
        tipos = {d["tipo"] for d in c.get("/api/estado").json()}
        assert {"temp", "comando"} <= tipos
        with c.websocket_connect("/ws") as ws:
            primeros = [ws.receive_json() for _ in range(2)]
            assert {d["tipo"] for d in primeros} == {"temp", "comando"}
