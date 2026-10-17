"""Contrato de fuente: algo que publica eventos en el bus mientras corre.

Cada fuente es una clase con `async def correr(self, bus)` que no
termina hasta que se cancela (CancelledError al apagar el servidor).
Si la fuente pierde el hardware, publica `estado_fuente` con
conectada=False y reintenta; NUNCA tumba el servidor ni inventa datos.

Las fuentes con E/S bloqueante (serie, cámara) corren su bucle en un
hilo (`asyncio.to_thread`) y publican con `bus.publicar_desde_hilo`.
"""
from __future__ import annotations

import importlib
from typing import Any, Protocol

from nucleo.bus import Bus


class Fuente(Protocol):
    async def correr(self, bus: Bus) -> None: ...


# nombre CLI -> "modulo:Clase". Import perezoso: arrancar en modo sim no
# debe exigir pyserial, mediapipe ni pyrealsense2.
REGISTRO: dict[str, str] = {
    "sim": "sim.clima:FuenteClimaSim",             # clima exterior/interior simulado (ordenador 2)
    "esp32": "captar.serial_bridge:FuenteSerie",   # ESP32-S3 de la maqueta por USB (ordenador 1)
    "realsense": "vision.pose:FuentePose",         # pose 3D D435i -> caída/desmayo (ordenador 1)
    "webcam": "vision.pose:FuentePose",            # pose 2D webcam
    "pose_sim": "vision.sim_vision:FuenteVisionSim",  # visión simulada: personas con etiquetas + pose + caída/desmayo (ordenador 1)
    "aforo_sim": "sim.aforo_sim:FuenteAforoSim",   # llegadas de gente simuladas
    "yolo": "vision.aforo:FuenteAforo",            # conteo real con cámara (ordenador 1)
}


def crear(nombre: str, **kw: Any) -> Fuente:
    mod, cls = REGISTRO[nombre].split(":")
    return getattr(importlib.import_module(mod), cls)(**kw)
