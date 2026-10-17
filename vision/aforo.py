"""Conteo de personas con la RealSense D435i + etiquetas (Ordenador 1 — PENDIENTE).

Decisión del equipo: la MISMA RealSense que ya hace pose/caídas cuenta personas.
Detector (YOLO clase person) + tracker (ByteTrack de ultralytics) -> cada persona
lleva etiqueta estable "Persona 3"; la profundidad da su posición (x, z) en metros
para colocar avatares en el gemelo 3D (evento `personas`).

Contrato: publicar `Evento("aforo", n:int, "yolo", refugio)` ~1 Hz, solo
cuando cambia o cada 5 s. Sin cámara o sin modelo: publicar
`estado_fuente` {"conectada": False, "detalle": ...} y reintentar; NUNCA
inventar un número (el servidor tiene `--aforo aforo_sim` para eso).

Privacidad (línea roja): NUNCA se guardan fotos ni vídeo de las personas. La imagen
vive solo en memoria del frame actual; sale únicamente el número, las etiquetas y
posiciones. Con --ver-camara se puede ver en directo /camara.mjpg (cajas + etiquetas)
para depurar, sin escribir a disco.
"""
from __future__ import annotations

import asyncio

from nucleo.bus import Bus
from nucleo.evento import Evento


class FuenteAforo:
    def __init__(self, camara: str = "realsense", modelo: str = "yolo11n.pt", refugio: str = "R1") -> None:
        self.camara = camara
        self.modelo = modelo
        self.refugio = refugio

    async def correr(self, bus: Bus) -> None:
        # TODO Ordenador 1: ultralytics YOLO (clase 0 = person) en un hilo + publicar_desde_hilo.
        while True:
            bus.publicar(Evento("estado_fuente", {"conectada": False, "detalle": "vision.aforo sin implementar"},
                                "yolo", self.refugio))
            await asyncio.sleep(5)
