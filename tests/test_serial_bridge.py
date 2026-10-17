import asyncio
import json
import queue

import pytest

from captar import serial_bridge
from captar.serial_bridge import FuenteSerie
from nucleo.bus import Bus
from nucleo.evento import Evento


class FakeSerial:
    """readline() espera poco (como el timeout real); `romper()` simula USB desenchufado."""

    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.escrito: list[bytes] = []
        self.cerrado = False
        self.roto = False

    def meter(self, linea):
        self.q.put(linea if isinstance(linea, bytes) else linea.encode())

    def romper(self):
        self.roto = True

    def readline(self):
        if self.roto or self.cerrado:
            raise OSError("device disconnected")
        try:
            return self.q.get(timeout=0.02)
        except queue.Empty:
            return b""

    def write(self, b):
        if self.roto:
            raise OSError("device disconnected")
        self.escrito.append(b)

    def close(self):
        self.cerrado = True


@pytest.fixture(autouse=True)
def reintento_rapido(monkeypatch):
    monkeypatch.setattr(serial_bridge, "REINTENTO_S", 0.05)


@pytest.fixture
def bus():
    b = Bus()
    return b


def grabar(bus):
    evs: list[Evento] = []
    bus.oyente(evs.append)
    return evs


async def esperar(cond, t=3.0):
    fin = asyncio.get_running_loop().time() + t
    while not cond():
        assert asyncio.get_running_loop().time() < fin, "timeout"
        await asyncio.sleep(0.01)


async def arrancar(bus, ser):
    f = FuenteSerie(abrir=lambda: ser)
    return f, asyncio.create_task(f.correr(bus))


async def parar(tarea):
    tarea.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarea


def medidas(evs):
    return {e.tipo: e.valor for e in evs if e.tipo != "estado_fuente"}


async def test_linea_completa(bus):
    evs, ser = grabar(bus), FakeSerial()
    _, t = await arrancar(bus, ser)
    ser.meter('{"temp": 27.4, "humedad": 48.0, "luz": 0.62, "presencia": true, "rele": false}\n')
    await esperar(lambda: len(medidas(evs)) == 5)
    assert medidas(evs) == {"temp": 27.4, "humedad": 48.0, "luz": 0.62,
                            "presencia": True, "rele": False}
    assert all(e.fuente == "esp32" for e in evs)
    await parar(t)


async def test_conexion_publica_estado(bus):
    evs, ser = grabar(bus), FakeSerial()
    _, t = await arrancar(bus, ser)
    await esperar(lambda: evs)
    assert evs[0].tipo == "estado_fuente" and evs[0].valor["conectada"] is True
    await parar(t)


async def test_campos_omitidos(bus):
    evs, ser = grabar(bus), FakeSerial()
    _, t = await arrancar(bus, ser)
    ser.meter('{"temp": 20.5, "presencia": false}\n')
    await esperar(lambda: len(medidas(evs)) == 2)
    assert medidas(evs) == {"temp": 20.5, "presencia": False}
    await parar(t)


async def test_basura_se_ignora_y_sigue(bus):
    evs, ser = grabar(bus), FakeSerial()
    _, t = await arrancar(bus, ser)
    for linea in ['{"temp": 2', "\n", "texto de arranque ESP-IDF\n", "[1,2]\n",
                  b"\xff\xfe\x00\n", '{"inventado": 5}\n',
                  '{"temp": "caliente", "humedad": 150, "luz": 2, "presencia": 1, "rele": null}\n',
                  '{"temp": NaN}\n', '{"temp": true}\n']:
        ser.meter(linea)
    ser.meter('{"temp": 22.0}\n')
    await esperar(lambda: medidas(evs).get("temp") == 22.0)
    assert [e.valor for e in evs if e.tipo == "temp"] == [22.0]
    assert medidas(evs) == {"temp": 22.0}
    await parar(t)


async def test_error_de_sensor_no_publica(bus):
    evs, ser = grabar(bus), FakeSerial()
    _, t = await arrancar(bus, ser)
    ser.meter('{"error": "dht: checksum"}\n')
    ser.meter('{"luz": 0.5}\n')
    await esperar(lambda: medidas(evs).get("luz") == 0.5)
    assert medidas(evs) == {"luz": 0.5}
    await parar(t)


async def test_comando_escribe_json_por_linea(bus):
    ser = FakeSerial()
    _, t = await arrancar(bus, ser)
    await esperar(lambda: bus.ultimo.get(("R1", "estado_fuente")))
    bus.publicar(Evento("comando", {"destino": "rele", "valor": True}, "reglas"))
    bus.publicar(Evento("comando", {"destino": "buzzer", "valor": 500}, "panel"))
    bus.publicar(Evento("comando", {"destino": "otro", "valor": 1}, "panel"))
    bus.publicar(Evento("comando", {"destino": "rele", "valor": "si"}, "panel"))
    assert [json.loads(b) for b in ser.escrito] == [{"rele": True}, {"buzzer": 500}]
    assert all(b.endswith(b"\n") for b in ser.escrito)
    await parar(t)


async def test_desconexion_y_reconexion(bus):
    evs = grabar(bus)
    sers = [FakeSerial(), FakeSerial()]
    intentos = []

    def abrir():
        intentos.append(1)
        if len(intentos) == 2:  # primer reintento: puerto aún ausente
            raise FileNotFoundError("/dev/ttyACM0")
        return sers[0] if len(intentos) == 1 else sers[1]

    t = asyncio.create_task(FuenteSerie(abrir=abrir).correr(bus))

    def estados():
        return [e.valor["conectada"] for e in evs if e.tipo == "estado_fuente"]

    await esperar(lambda: estados() == [True])
    sers[0].romper()
    await esperar(lambda: len(estados()) >= 3)
    # una sola notificación por caída aunque falle el reintento
    assert estados() == [True, False, True]
    assert len(intentos) == 3 and sers[0].cerrado
    sers[1].meter('{"temp": 30.0}\n')
    await esperar(lambda: medidas(evs).get("temp") == 30.0)
    await parar(t)


async def test_puerto_inexistente_avisa_una_vez(bus):
    evs = grabar(bus)
    n = []

    def abrir():
        n.append(1)
        raise FileNotFoundError("sin puerto")

    t = asyncio.create_task(FuenteSerie(abrir=abrir).correr(bus))
    await esperar(lambda: len(n) >= 4)
    st = [e for e in evs if e.tipo == "estado_fuente"]
    assert len(st) == 1
    assert st[0].valor["conectada"] is False and "sin puerto" in st[0].valor["detalle"]
    await parar(t)


async def test_cancelacion_limpia(bus):
    ser = FakeSerial()
    _, t = await arrancar(bus, ser)
    await esperar(lambda: bus.ultimo.get(("R1", "estado_fuente")))
    assert len(bus._oyentes) == 1
    await parar(t)
    assert ser.cerrado
    assert bus._oyentes == []
