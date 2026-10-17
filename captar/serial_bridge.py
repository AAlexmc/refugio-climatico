"""Puente ESP32-S3 <-> bus por USB CDC (JSON por línea, ver docs/contratos.md).

Lectura bloqueante en un hilo (`asyncio.to_thread`); los eventos vuelven al
loop con `bus.publicar_desde_hilo`. Los comandos `rele`/`buzzer` del bus se
escriben al puerto bajo un lock. Sin puerto: `estado_fuente` desconectada
(una vez por caída) y reintento cada 2 s; nunca se inventan datos.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import threading
from collections.abc import Callable
from typing import Any

from nucleo.bus import Bus
from nucleo.evento import Evento

log = logging.getLogger(__name__)

REINTENTO_S = 2.0
BUZZER_MS_DEFECTO = 500


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _temp(v: Any) -> bool:
    return _num(v) and -40 <= v <= 125


def _humedad(v: Any) -> bool:
    return _num(v) and 0 <= v <= 100


def _luz(v: Any) -> bool:
    return _num(v) and 0 <= v <= 1


def _bool(v: Any) -> bool:
    return isinstance(v, bool)


# campo de la línea JSON -> validador (el nombre coincide con el tipo de evento)
CAMPOS: dict[str, Callable[[Any], bool]] = {
    "temp": _temp,
    "humedad": _humedad,
    "luz": _luz,
    "presencia": _bool,
    "rele": _bool,
}


def _abrir_defecto(puerto: str, baudios: int):
    import serial  # import perezoso: modo sim no exige pyserial

    return serial.Serial(puerto, baudios, timeout=1, write_timeout=1)


class FuenteSerie:
    def __init__(self, puerto: str = "/dev/ttyACM0", baudios: int = 115200, *,
                 abrir: Callable[[], Any] | None = None) -> None:
        self.puerto = puerto
        self.baudios = baudios
        self._abrir = abrir or (lambda: _abrir_defecto(puerto, baudios))
        self._ser: Any = None
        self._lock = threading.Lock()

    # ---- ESP32 -> bus -------------------------------------------------
    def _procesar_linea(self, bus: Bus, raw: bytes | str) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        raw = raw.strip()
        if not raw:
            return
        try:
            d = json.loads(raw)
        except ValueError:
            log.debug("línea no JSON ignorada: %r", raw)
            return
        if not isinstance(d, dict):
            log.debug("JSON no objeto ignorado: %r", raw)
            return
        if "error" in d:
            log.debug("error del firmware: %r", d["error"])
        for campo, valido in CAMPOS.items():
            if campo not in d:
                continue
            v = d[campo]
            if not valido(v):
                log.debug("valor inválido %s=%r", campo, v)
                continue
            bus.publicar_desde_hilo(Evento(campo, v, "esp32"))
        for campo in d.keys() - CAMPOS.keys() - {"error"}:
            log.debug("campo desconocido ignorado: %s", campo)

    def _leer(self, bus: Bus, ser: Any, parar: threading.Event) -> None:
        """Hilo lector. Sale al pedir parada; una excepción = caída del puerto."""
        while not parar.is_set():
            linea = ser.readline()
            if linea:
                self._procesar_linea(bus, linea)

    # ---- bus -> ESP32 -------------------------------------------------
    @staticmethod
    def _payload(destino: str, valor: Any) -> dict | None:
        if destino == "rele":
            return {"rele": valor} if isinstance(valor, bool) else None
        if destino == "buzzer":
            if valor is True:
                return {"buzzer": BUZZER_MS_DEFECTO}
            if _num(valor) and valor > 0:
                return {"buzzer": int(valor)}
        return None

    def _comando(self, ev: Evento) -> None:
        if ev.tipo != "comando" or not isinstance(ev.valor, dict):
            return
        destino = ev.valor.get("destino")
        if destino not in ("rele", "buzzer"):
            return
        payload = self._payload(destino, ev.valor.get("valor"))
        if payload is None:
            log.debug("comando inválido ignorado: %r", ev.valor)
            return
        linea = (json.dumps(payload) + "\n").encode()
        with self._lock:
            if self._ser is None:
                log.debug("comando sin puerto abierto: %r", payload)
                return
            try:
                self._ser.write(linea)
            except Exception as e:  # el lector detectará la caída
                log.debug("fallo al escribir: %s", e)

    # ---- ciclo de vida ------------------------------------------------
    @staticmethod
    def _estado(bus: Bus, conectada: bool, detalle: str) -> None:
        bus.publicar(Evento("estado_fuente",
                            {"conectada": conectada, "detalle": detalle}, "esp32"))

    async def correr(self, bus: Bus) -> None:
        if bus._loop is None:
            bus.enlazar_loop(asyncio.get_running_loop())
        baja = bus.oyente(self._comando)
        caida_avisada = False
        try:
            while True:
                try:
                    ser = await asyncio.to_thread(self._abrir)
                except Exception as e:
                    if not caida_avisada:
                        self._estado(bus, False, f"{self.puerto}: {e}")
                        caida_avisada = True
                    await asyncio.sleep(REINTENTO_S)
                    continue
                with self._lock:
                    self._ser = ser
                caida_avisada = False
                self._estado(bus, True, self.puerto)
                parar = threading.Event()
                try:
                    await asyncio.to_thread(self._leer, bus, ser, parar)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self._estado(bus, False, f"{self.puerto}: {e}")
                    caida_avisada = True
                    await asyncio.sleep(REINTENTO_S)
                finally:
                    parar.set()
                    self._cerrar()
        finally:
            baja()
            self._cerrar()

    def _cerrar(self) -> None:
        with self._lock:
            ser, self._ser = self._ser, None
        if ser is not None:
            try:
                ser.close()
            except Exception as e:
                log.debug("fallo al cerrar: %s", e)
