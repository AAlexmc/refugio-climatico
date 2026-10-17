import asyncio

from fastapi.testclient import TestClient

from control.demo import Director
from nucleo.bus import Bus
from servidor.app import crear_app


def test_director_publica_guion_y_desmayo():
    async def run():
        bus = Bus()
        bus.enlazar_loop(asyncio.get_running_loop())
        vistos = []
        bus.oyente(vistos.append)
        d = Director(bus)
        d.iniciar(0.01)
        assert d.activa
        await asyncio.sleep(1.5)
        assert not d.activa
        return vistos

    vistos = asyncio.run(run())
    pasos = [e.valor["paso"] for e in vistos if e.tipo == "guion"]
    assert pasos == [1, 2, 3, 4, 5, 6, 7, 0]
    des = [e.valor["activo"] for e in vistos if e.tipo == "desmayo"]
    assert des == [True, False]
    assert any(e.tipo == "comando" and e.valor["destino"] == "atendido" for e in vistos)


def test_api_demo_invalida_y_refugios():
    with TestClient(crear_app([])) as c:
        assert c.post("/api/demo", json={"accion": "x"}).status_code == 422
        assert c.post("/api/demo", json={"accion": "iniciar", "escala": "a"}).status_code == 422
        r = c.post("/api/demo", json={"accion": "iniciar", "escala": 0.01})
        assert r.status_code == 200 and r.json()["ok"]
        assert c.post("/api/demo", json={"accion": "parar"}).json()["activa"] is False
        c.post("/api/evento", json={"tipo": "aforo", "valor": 7, "fuente": "panel"})
        lst = c.get("/api/refugios").json()
        assert [r["id"] for r in lst] == ["R1"]
        assert lst[0]["aforo"] == 7 and lst[0]["aforo_max"] == 20
